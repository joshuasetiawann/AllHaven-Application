# backend/app/services/sync_engine.py
"""Incremental two-way sync engine: push_table + pull_table (LWW + echo suppression).

Watermark cursors live in ``sync_state``. Pull applies remote rows by Last-Write-Wins
on ``updated_at``; echo suppression advances the push watermark after pull so the same
rows are not re-sent on the next push.

Global constraints (mirrors supabase_sync_service semantics):
- Never raises to callers; failures logged at DEBUG.
- Local Postgres is the source of truth.
- Service-role key is never logged.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.domain.sync_state import SyncState
from app.services import supabase_sync_service as mirror
from app.services import supabase_auth_service
from app.services.sync_registry import SyncSpec, SYNCED_TABLES

log = logging.getLogger(__name__)


def _to_utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Compare instants, not wall-clocks. Aware -> convert to UTC then drop tz; naive assumed UTC."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Watermark helpers
# ---------------------------------------------------------------------------

def _state(db: Session, ws: uuid.UUID, table: str, direction: str) -> SyncState:
    """Return (or create) the watermark row for (ws, table, direction)."""
    row = (
        db.query(SyncState)
        .filter(
            SyncState.workspace_id == ws,
            SyncState.table_name == table,
            SyncState.direction == direction,
        )
        .one_or_none()
    )
    if row is None:
        row = SyncState(workspace_id=ws, table_name=table, direction=direction)
        db.add(row)
        db.flush()
    return row


def _bump(state: SyncState, value: Optional[datetime], pk: Optional[uuid.UUID]) -> None:
    """Advance the watermark only forward (monotone).

    Normalises to offset-naive UTC before comparison so that tz-aware datetimes
    (from remote JSON) compare correctly with tz-naive values read back from
    SQLite (which strips tzinfo on storage).

    Stores the UTC-naive form of ``value`` into ``state.last_value`` so that
    the in-Python comparison and the SQL ``col > state.last_value`` filter both
    operate on the same UTC-naive convention.
    """
    if value is None:
        return
    _new = _to_utc_naive(value)
    _cur = _to_utc_naive(state.last_value)
    if _cur is None or _new >= _cur:
        state.last_value = _new  # store UTC-naive so SQL filter agrees
        state.last_pk = pk


# ---------------------------------------------------------------------------
# Task 5: push_table — incremental local→remote
# ---------------------------------------------------------------------------

def push_table(
    db: Session,
    url: str,
    key: str,
    ws: uuid.UUID,
    member_ids: list[uuid.UUID],
    spec: SyncSpec,
    *,
    upsert: Callable[[str, list[dict]], None],
) -> int:
    """Push local rows newer than the current push watermark to Supabase.

    Args:
        db: SQLAlchemy session.
        url: Supabase project URL (unused by injected upsert in tests).
        key: Service-role key (unused by injected upsert in tests).
        ws: Workspace UUID to scope the query.
        member_ids: Member UUIDs for user-scoped tables (e.g. profiles).
        spec: ``SyncSpec`` describing the table.
        upsert: Injected callable ``(table_name, rows) -> None``.  Tests pass a
            fake; production callers pass ``_http_upsert(url, key)``.

    Returns:
        Number of rows pushed.
    """
    state = _state(db, ws, spec.table_name, "push")
    col = getattr(spec.model, spec.watermark_col)
    q = db.query(spec.model).filter(spec.scope(ws, member_ids))
    if state.last_value is not None:
        q = q.filter(col > state.last_value)
    rows = q.order_by(col.asc()).all()
    if not rows:
        return 0
    upsert(spec.table_name, [mirror._serialize(r) for r in rows])
    last = rows[-1]
    _bump(state, getattr(last, spec.watermark_col), getattr(last, "id", None))
    db.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Task 6: pull_table — remote→local LWW merge + echo suppression
# ---------------------------------------------------------------------------

def lww_apply(db: Session, spec: SyncSpec, row: dict) -> Optional[datetime]:
    """Apply one remote row by PK using Last-Write-Wins semantics.

    Rules:
    - Absent locally → insert unconditionally.
    - Append-only table and row present → skip (immutable).
    - Row present and NOT append-only:
        - incoming ``updated_at`` ≥ local ``updated_at`` → overwrite.
        - incoming is strictly older → keep local (LWW: local wins).

    Returns:
        The ``updated_at`` (or ``created_at``) of the applied row, or ``None``
        if the row was skipped.
    """
    kwargs = mirror._deserialize(spec.model, row)
    pk = kwargs.get("id")
    incoming_ts: Optional[datetime] = kwargs.get("updated_at") or kwargs.get("created_at")
    existing = db.get(spec.model, pk) if pk is not None else None

    if existing is None:
        db.add(spec.model(**kwargs))
        return incoming_ts

    if spec.append_only:
        return None  # immutable; already present — never update

    local_ts: Optional[datetime] = getattr(existing, "updated_at", None)
    if local_ts is not None and incoming_ts is not None:
        # Convert to UTC-naive instants so wall-clock numbers from non-UTC
        # sessions cannot make an older row look newer (LWW correctness).
        if _to_utc_naive(incoming_ts) < _to_utc_naive(local_ts):
            return None  # local is strictly newer → LWW keeps local

    for k, v in kwargs.items():
        setattr(existing, k, v)
    return incoming_ts


def pull_table(
    db: Session,
    url: str,
    key: str,
    ws: uuid.UUID,
    member_ids: list[uuid.UUID],
    spec: SyncSpec,
    *,
    fetch: Callable[[str, str, Optional[datetime]], list[dict]],
) -> int:
    """Pull remote rows since the last pull watermark and apply them (LWW merge).

    After applying, advances the **pull** watermark to the newest row seen, and
    bumps the **push** watermark past the max applied ``updated_at`` so that
    ``push_table`` does NOT re-send the rows we just received (echo suppression).

    Args:
        db: SQLAlchemy session.
        url: Supabase URL (forwarded to real fetch; unused by test fake).
        key: Service-role key (forwarded to real fetch; unused by test fake).
        ws: Workspace UUID.
        member_ids: Member UUIDs for user-scoped tables.
        spec: ``SyncSpec`` describing the table.
        fetch: Injected callable ``(table_name, watermark_col, since) -> list[dict]``.

    Returns:
        Number of rows applied (LWW-skipped rows not counted).
    """
    pull_state = _state(db, ws, spec.table_name, "pull")
    incoming = fetch(spec.table_name, spec.watermark_col, pull_state.last_value)

    applied = 0
    max_applied_ts: Optional[datetime] = None

    for row in incoming:
        ts = lww_apply(db, spec, row)
        if ts is not None:
            applied += 1
            if max_applied_ts is None or ts > max_applied_ts:
                max_applied_ts = ts

    if incoming:
        # Advance pull watermark to the newest row *seen* (even if LWW-skipped),
        # so we make progress and don't re-fetch the same rows forever.
        seen_ts: list[datetime] = []
        for r in incoming:
            kwargs = mirror._deserialize(spec.model, r)
            t = kwargs.get(spec.watermark_col)
            if t is not None:
                seen_ts.append(t)
        if seen_ts:
            _bump(pull_state, max(seen_ts), None)

    if max_applied_ts is not None:
        # Echo suppression: advance push watermark past the rows we just applied,
        # so the next push_table call does NOT re-send them to Supabase.
        _bump(_state(db, ws, spec.table_name, "push"), max_applied_ts, None)

    db.commit()
    return applied


# ---------------------------------------------------------------------------
# Task 7: HTTP adapters + sync_two_way orchestrator
# ---------------------------------------------------------------------------

def _http_upsert(url: str, key: str) -> Callable[[str, list[dict]], None]:
    """Return a upsert callable that POSTs via supabase_sync_service._upsert (DRY reuse)."""
    def upsert(table: str, rows: list[dict]) -> None:
        mirror._upsert(url, key, table, rows)
    return upsert


def _http_fetch(url: str, key: str) -> Callable[[str, str, Optional[datetime]], list[dict]]:
    """Return a fetch callable that GETs rows from Supabase newer than ``since``."""
    def fetch(table: str, col: str, since: Optional[datetime]) -> list[dict]:
        params = ["select=*", f"order={col}.asc", "limit=1000"]
        if since is not None:
            params.append(f"{col}=gt.{urllib.parse.quote(since.isoformat())}")
        full = f"{url.rstrip('/')}/rest/v1/{table}?{'&'.join(params)}"
        req = urllib.request.Request(
            full,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "[]")
    return fetch


def _member_ids(db: Session, ws: uuid.UUID) -> list[uuid.UUID]:
    """Return user_ids of all workspace members (for user-scoped tables like profiles)."""
    from app.domain.workspaces import WorkspaceMember
    return [m.user_id for m in db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == ws).all()]


def sync_two_way(db: Session, principal) -> dict:
    """Incremental two-way sync: pull remote→local then push local→remote for all synced tables.

    Best-effort: never raises; per-table failures are logged at DEBUG and skipped.
    Uses service-role key (RLS blocks anon key).

    Returns:
        dict with keys: status ("ok"|"skipped"|"error"), pulled, pushed, tables.
    """
    try:
        url, key = supabase_auth_service.get_service_credentials(db, principal.workspace_id)
        if not url or not key:
            return {"status": "skipped", "reason": "no_credentials"}
        ws = principal.workspace_id
        members = _member_ids(db, ws)
        upsert = _http_upsert(url, key)
        fetch = _http_fetch(url, key)
        pulled = pushed = 0
        for spec in SYNCED_TABLES:
            try:
                pulled += pull_table(db, url, key, ws, members, spec, fetch=fetch)
                pushed += push_table(db, url, key, ws, members, spec, upsert=upsert)
            except Exception as exc:  # per-table isolation; keep going
                log.debug("sync skipped for %s: %s", spec.table_name, exc)
        return {"status": "ok", "pulled": pulled, "pushed": pushed, "tables": len(SYNCED_TABLES)}
    except Exception as exc:
        log.debug("sync_two_way failed: %s", exc)
        return {"status": "error", "reason": str(exc)}
