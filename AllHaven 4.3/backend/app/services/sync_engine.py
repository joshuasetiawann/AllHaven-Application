# backend/app/services/sync_engine.py
"""Incremental two-way sync engine: push_table + pull_table (tenant-safe LWW).

Watermark cursors live in ``sync_state``. Pull applies remote rows by Last-Write-Wins
on ``updated_at``. Push cursors advance only after a successful remote upsert; pull
must never advance them because doing so can skip older local writes that have not
yet reached Supabase.

Global constraints (mirrors supabase_sync_service semantics):
- Never raises to callers; failures logged at DEBUG.
- Local Postgres is the source of truth.
- Service-role key is never logged.
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

import sqlalchemy
from sqlalchemy import UniqueConstraint, and_, or_, select
from sqlalchemy.orm import Session

from app.domain.sync_state import SyncState
from app.services import supabase_sync_service as mirror
from app.services import supabase_auth_service
from app.services.sync_registry import SyncSpec, SYNCED_TABLES

log = logging.getLogger(__name__)
_HTTP_PAGE_SIZE = 1000


FetchRows = Callable[
    [SyncSpec, uuid.UUID, list[uuid.UUID], Optional[datetime], Optional[uuid.UUID]],
    list[dict],
]


def _to_utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Compare instants, not wall-clocks. Aware -> convert to UTC then drop tz; naive assumed UTC."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=None)


def _as_uuid(value: object) -> Optional[uuid.UUID]:
    """Return *value* as a UUID, or ``None`` for malformed/unset values."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _cursor_is_later(
    value: datetime,
    pk: uuid.UUID,
    current_value: Optional[datetime],
    current_pk: Optional[uuid.UUID],
) -> bool:
    """Compare deterministic ``(timestamp, id)`` cursors."""
    new_value = _to_utc_naive(value)
    old_value = _to_utc_naive(current_value)
    if old_value is None or new_value > old_value:
        return True
    if new_value < old_value:
        return False
    old_pk = _as_uuid(current_pk)
    return old_pk is None or pk.int > old_pk.int


def _row_in_scope(
    spec: SyncSpec,
    row: dict,
    ws: uuid.UUID,
    member_ids: list[uuid.UUID],
) -> bool:
    """Validate an incoming row against the active tenant before deserializing it.

    The HTTP request is already tenant-filtered, but this second check prevents a
    buggy/malicious PostgREST response or test adapter from writing another
    workspace's data through the service-role connection.
    """
    if spec.table_name == "workspaces":
        return _as_uuid(row.get("id")) == ws
    if spec.user_scoped:  # profiles are scoped through workspace membership
        row_id = _as_uuid(row.get("id"))
        allowed = {_as_uuid(member_id) for member_id in member_ids}
        allowed.discard(None)
        return row_id is not None and row_id in allowed
    return _as_uuid(row.get("workspace_id")) == ws


def _existing_in_scope(
    spec: SyncSpec,
    existing: object,
    ws: uuid.UUID,
    member_ids: list[uuid.UUID],
) -> bool:
    """Validate the tenant of a local row selected by an incoming primary key.

    Validating only the remote payload is insufficient: a malicious response can
    claim workspace A while reusing the primary key of a row in workspace B. LWW
    would otherwise find that B row and rewrite its ``workspace_id`` and contents.
    """
    if spec.table_name == "workspaces":
        return _as_uuid(getattr(existing, "id", None)) == ws
    if spec.user_scoped:
        existing_id = _as_uuid(getattr(existing, "id", None))
        allowed = {_as_uuid(member_id) for member_id in member_ids}
        allowed.discard(None)
        return existing_id is not None and existing_id in allowed
    return _as_uuid(getattr(existing, "workspace_id", None)) == ws


def _incoming_cursor(spec: SyncSpec, row: dict) -> Optional[tuple[datetime, uuid.UUID]]:
    """Parse the required deterministic cursor from a remote row."""
    try:
        kwargs = mirror._deserialize(spec.model, row)
    except (TypeError, ValueError, OverflowError):
        return None
    value = kwargs.get(spec.watermark_col)
    pk = _as_uuid(kwargs.get("id"))
    if not isinstance(value, datetime) or pk is None:
        return None
    return value, pk


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
    new_pk = _as_uuid(pk)
    if new_pk is None:
        return
    if _cursor_is_later(value, new_pk, state.last_value, state.last_pk):
        state.last_value = _to_utc_naive(value)  # SQL filter uses UTC-naive values
        state.last_pk = new_pk


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
        if state.last_pk is None:
            # Upgrade a legacy timestamp-only cursor safely: replay the boundary
            # once rather than permanently skipping rows that share its timestamp.
            q = q.filter(col >= state.last_value)
        else:
            q = q.filter(
                or_(
                    col > state.last_value,
                    and_(col == state.last_value, spec.model.id > state.last_pk),
                )
            )
    rows = q.order_by(col.asc(), spec.model.id.asc()).all()
    if not rows:
        return 0
    upsert(spec.table_name, [mirror._serialize(r) for r in rows])
    last = rows[-1]
    _bump(state, getattr(last, spec.watermark_col), getattr(last, "id", None))
    db.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Task 6: pull_table — remote→local tenant-safe LWW merge
# ---------------------------------------------------------------------------

def _unique_keys(model) -> list[list]:
    """Return every UNIQUE column-set of *model*'s table (PK excluded).

    Covers all three ways uniqueness is declared in ``app.domain``: ``unique=True``
    on the column, a composite ``UniqueConstraint``, and a unique ``Index``
    (how ``dedup_key`` is declared). Overlapping sets are harmless — the caller
    just checks one of them twice.
    """
    table = model.__table__
    keys: list[list] = [[c] for c in table.columns if c.unique and not c.primary_key]
    keys += [list(c.columns) for c in table.constraints if isinstance(c, UniqueConstraint)]
    keys += [list(i.columns) for i in table.indexes if i.unique]
    return keys


def _unique_twin(db: Session, model, kwargs: dict):
    """Return the local row already holding one of *model*'s UNIQUE values, else None."""
    by_name = {c.name: c for c in model.__table__.columns}
    attr_of = {a.columns[0].name: a.key for a in sqlalchemy.inspect(model).mapper.column_attrs}
    for cols in _unique_keys(model):
        values = [kwargs.get(attr_of.get(c.name, c.name)) for c in cols]
        if any(v is None for v in values):
            continue  # NULL never collides in a UNIQUE index
        conds = [by_name[c.name] == v for c, v in zip(cols, values)]
        twin = db.scalar(select(model).where(*conds).limit(1))
        if twin is not None:
            return twin
    return None


def lww_apply(
    db: Session,
    spec: SyncSpec,
    row: dict,
    *,
    workspace_id: Optional[uuid.UUID] = None,
    member_ids: Optional[list[uuid.UUID]] = None,
) -> Optional[datetime]:
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
    if workspace_id is not None and not _row_in_scope(
        spec, row, workspace_id, member_ids or []
    ):
        log.debug("Rejected out-of-scope sync row for table %s", spec.table_name)
        return None

    kwargs = mirror._deserialize(spec.model, row)
    pk = kwargs.get("id")
    incoming_ts: Optional[datetime] = kwargs.get("updated_at") or kwargs.get("created_at")
    existing = db.get(spec.model, pk) if pk is not None else None

    if (
        existing is not None
        and workspace_id is not None
        and not _existing_in_scope(spec, existing, workspace_id, member_ids or [])
    ):
        log.warning(
            "Rejected sync primary-key collision outside workspace for table %s",
            spec.table_name,
        )
        return None

    if existing is None:
        # Cross-device idempotency: this PK is new here, but a local row may already
        # own one of the table's UNIQUE keys — the same entity minted under a different
        # PK by another device (a profile with this email, a proposal with this
        # dedup_key, an integration for this workspace+provider). Inserting would raise
        # mid-cycle and abort the sync, so keep local and skip.
        if _unique_twin(db, spec.model, kwargs) is not None:
            return None
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
    fetch: FetchRows,
) -> int:
    """Pull remote rows since the last pull watermark and apply them (LWW merge).

    After applying, advances only the **pull** watermark to the newest row seen.
    A pulled row may be re-upserted once by the following push, which is safe and
    idempotent. Advancing the global push cursor here would be unsafe because a
    local, never-pushed row can have an older timestamp than the remote row.

    Args:
        db: SQLAlchemy session.
        url: Supabase URL (forwarded to real fetch; unused by test fake).
        key: Service-role key (forwarded to real fetch; unused by test fake).
        ws: Workspace UUID.
        member_ids: Member UUIDs for user-scoped tables.
        spec: ``SyncSpec`` describing the table.
        fetch: Injected callable receiving ``(spec, workspace_id, member_ids,
            cursor_timestamp, cursor_id)``.

    Returns:
        Number of rows applied (LWW-skipped rows not counted).
    """
    pull_state = _state(db, ws, spec.table_name, "pull")
    incoming = fetch(spec, ws, member_ids, pull_state.last_value, pull_state.last_pk)

    applied = 0
    max_seen_ts: Optional[datetime] = None
    max_seen_pk: Optional[uuid.UUID] = None

    for row in incoming:
        if not _row_in_scope(spec, row, ws, member_ids):
            log.debug("Rejected out-of-scope sync row for table %s", spec.table_name)
            continue
        cursor = _incoming_cursor(spec, row)
        if cursor is None:
            log.debug("Rejected sync row without a valid cursor for table %s", spec.table_name)
            continue
        row_ts, row_pk = cursor
        existing = db.get(spec.model, row_pk)
        if existing is not None and not _existing_in_scope(
            spec, existing, ws, member_ids
        ):
            log.warning(
                "Rejected sync primary-key collision outside workspace for table %s",
                spec.table_name,
            )
            continue
        if _cursor_is_later(row_ts, row_pk, max_seen_ts, max_seen_pk):
            max_seen_ts, max_seen_pk = row_ts, row_pk

        ts = lww_apply(
            db,
            spec,
            row,
            workspace_id=ws,
            member_ids=member_ids,
        )
        if ts is not None:
            applied += 1

    if max_seen_ts is not None and max_seen_pk is not None:
        # Advance to the newest valid, in-scope row seen even when LWW kept the
        # local version, so a stale remote row is not fetched forever.
        _bump(pull_state, max_seen_ts, max_seen_pk)

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


def _cursor_iso(value: datetime | str) -> str:
    """Render a cursor timestamp as an explicit UTC ISO-8601 value."""
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat()


def _tenant_filter(
    spec: SyncSpec,
    ws: uuid.UUID,
    member_ids: list[uuid.UUID],
) -> Optional[tuple[str, str]]:
    """Return the PostgREST filter that confines *spec* to one workspace."""
    if spec.table_name == "workspaces":
        return "id", f"eq.{ws}"
    if spec.user_scoped:
        members = sorted(
            {parsed for value in member_ids if (parsed := _as_uuid(value)) is not None},
            key=lambda item: item.int,
        )
        if not members:
            return None
        return "id", f"in.({','.join(str(member) for member in members)})"
    return "workspace_id", f"eq.{ws}"


def _http_fetch(url: str, key: str) -> FetchRows:
    """Return a tenant-scoped, cursor-paginated Supabase fetch callable.

    PostgREST's default maximum result size is commonly 1,000 rows. Paging on
    ``(watermark, id)`` avoids both that truncation and timestamp-tie loss.
    """
    def fetch(
        spec: SyncSpec,
        ws: uuid.UUID,
        member_ids: list[uuid.UUID],
        since: Optional[datetime],
        since_pk: Optional[uuid.UUID],
    ) -> list[dict]:
        tenant_filter = _tenant_filter(spec, ws, member_ids)
        if tenant_filter is None:  # no profiles are in this workspace
            return []

        table = spec.table_name
        col = spec.watermark_col
        cursor_value: datetime | str | None = since
        cursor_pk = _as_uuid(since_pk)
        rows: list[dict] = []
        previous_page_cursor: Optional[tuple[str, uuid.UUID]] = None

        while True:
            params: list[tuple[str, str]] = [
                ("select", "*"),
                tenant_filter,
                ("order", f"{col}.asc,id.asc"),
                ("limit", str(_HTTP_PAGE_SIZE)),
            ]
            if cursor_value is not None:
                cursor_iso = _cursor_iso(cursor_value)
                if cursor_pk is None:
                    # Timestamp-only state was written by pre-cursor releases.
                    # Replay the boundary once so equal-timestamp rows are recovered.
                    params.append((col, f"gte.{cursor_iso}"))
                else:
                    params.append(
                        (
                            "or",
                            (
                                f"({col}.gt.{cursor_iso},"
                                f"and({col}.eq.{cursor_iso},id.gt.{cursor_pk}))"
                            ),
                        )
                    )

            query = urllib.parse.urlencode(params, safe="(),.*")
            full = f"{url.rstrip('/')}/rest/v1/{table}?{query}"
            req = urllib.request.Request(
                full,
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                page = json.loads(resp.read().decode() or "[]")
            if not isinstance(page, list) or any(not isinstance(row, dict) for row in page):
                raise ValueError(f"Invalid PostgREST response for {table}")

            rows.extend(page)
            if len(page) < _HTTP_PAGE_SIZE:
                break

            last = page[-1]
            raw_value = last.get(col)
            next_pk = _as_uuid(last.get("id"))
            if not isinstance(raw_value, (str, datetime)) or next_pk is None:
                raise ValueError(f"PostgREST page for {table} has no deterministic cursor")
            next_cursor = (_cursor_iso(raw_value), next_pk)
            if next_cursor == previous_page_cursor:
                raise RuntimeError(f"PostgREST pagination made no progress for {table}")
            previous_page_cursor = next_cursor
            cursor_value, cursor_pk = next_cursor

        return rows

    return fetch


def _member_ids(db: Session, ws: uuid.UUID) -> list[uuid.UUID]:
    """Return user_ids of all workspace members (for user-scoped tables like profiles)."""
    from app.domain.workspaces import WorkspaceMember
    return [m.user_id for m in db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == ws).all()]


def _discover_remote_members(
    db: Session,
    fetch: FetchRows,
    ws: uuid.UUID,
    local_member_ids: list[uuid.UUID],
) -> tuple[Optional[list[dict]], list[uuid.UUID]]:
    """Prefetch membership changes so new member profiles can be pulled first.

    ``workspace_members.user_id`` has a foreign key to ``profiles.id``. The
    profile endpoint is user-scoped, so a newly-added remote member is not in
    the local member list yet. Fetching (but not applying) membership rows first
    lets the profile pull include those user IDs while preserving FK-safe apply
    order: profiles -> workspaces -> memberships.

    ``None`` means discovery failed and the normal table pass should retry the
    membership fetch so per-table error handling remains authoritative.
    """
    member_spec = next(
        (spec for spec in SYNCED_TABLES if spec.table_name == "workspace_members"),
        None,
    )
    if member_spec is None:
        return None, list(local_member_ids)

    state = _state(db, ws, member_spec.table_name, "pull")
    try:
        rows = fetch(
            member_spec,
            ws,
            local_member_ids,
            state.last_value,
            state.last_pk,
        )
    except Exception:
        db.rollback()
        log.debug("Remote membership discovery failed", exc_info=True)
        return None, list(local_member_ids)

    discovered = {
        parsed
        for value in local_member_ids
        if (parsed := _as_uuid(value)) is not None
    }
    for row in rows:
        if not _row_in_scope(member_spec, row, ws, local_member_ids):
            continue
        if _incoming_cursor(member_spec, row) is None:
            continue
        user_id = _as_uuid(row.get("user_id"))
        if user_id is not None:
            discovered.add(user_id)
    return rows, sorted(discovered, key=lambda value: value.int)


def _profile_fetch_with_missing(
    db: Session,
    fetch: FetchRows,
) -> FetchRows:
    """Fetch old profiles that become newly relevant through membership.

    A pre-existing profile can be much older than this workspace's profile
    watermark. For member IDs not present locally, perform an unwatermarked,
    ID-scoped fetch in addition to the incremental fetch. Results are de-duped
    by primary key before LWW apply.
    """
    def fetch_profiles(
        spec: SyncSpec,
        ws: uuid.UUID,
        member_ids: list[uuid.UUID],
        since: Optional[datetime],
        since_pk: Optional[uuid.UUID],
    ) -> list[dict]:
        rows: list[dict] = []
        if since is not None:
            missing = [
                member_id
                for member_id in member_ids
                if db.get(spec.model, member_id) is None
            ]
            if missing:
                rows.extend(fetch(spec, ws, missing, None, None))
        rows.extend(fetch(spec, ws, member_ids, since, since_pk))

        by_id: dict[uuid.UUID, dict] = {}
        malformed: list[dict] = []
        for row in rows:
            row_id = _as_uuid(row.get("id"))
            if row_id is None:
                malformed.append(row)
            else:
                by_id[row_id] = row
        return [*by_id.values(), *malformed]

    return fetch_profiles


# ---------------------------------------------------------------------------
# Task 9: visible sync status
# ---------------------------------------------------------------------------

def last_sync_status(db: Session, ws: uuid.UUID) -> dict:
    """Return a summary of watermark state for the given workspace.

    Returns:
        dict with:
            configured (bool): True if any SyncState rows exist for this workspace.
            tables (int): number of distinct table names with watermarks.
            watermarks (list): each entry is {"table", "direction", "last_value"}.
    """
    rows = db.query(SyncState).filter(SyncState.workspace_id == ws).all()
    return {
        "configured": bool(rows),
        "tables": len({r.table_name for r in rows}),
        "watermarks": [
            {
                "table": r.table_name,
                "direction": r.direction,
                "last_value": r.last_value.isoformat() if r.last_value else None,
            }
            for r in rows
        ],
    }


_workspace_locks: dict[uuid.UUID, threading.Lock] = {}
_locks_guard = threading.Lock()


def _workspace_lock(ws: uuid.UUID) -> threading.Lock:
    """One lock per workspace, created on first use (bounded by workspace count)."""
    with _locks_guard:
        return _workspace_locks.setdefault(ws, threading.Lock())


def sync_two_way(db: Session, principal) -> dict:
    """Incremental two-way sync: pull remote→local then push local→remote for all synced tables.

    Best-effort: never raises; per-table failures are logged at DEBUG and skipped.
    Uses service-role key (RLS blocks anon key).

    Only one pass per workspace runs at a time. The 15s scheduler and the per-write
    trigger both call this, and two concurrent passes insert the same ``sync_state``
    watermark row twice (uq_sync_state_ws_table_dir), aborting each other's
    transaction. An already-running pass covers the same rows, so overlap is skipped
    rather than queued — no thread pile-up under heavy writes.

    Returns:
        dict with keys: status ("ok"|"skipped"|"error"), pulled, pushed, tables.
    """
    lock = _workspace_lock(principal.workspace_id)
    if not lock.acquire(blocking=False):
        return {"status": "skipped", "reason": "already_running"}
    try:
        return _sync_two_way_locked(db, principal)
    finally:
        lock.release()


def _sync_two_way_locked(db: Session, principal) -> dict:
    """The actual sync pass; callers must hold the workspace lock."""
    try:
        url, key = supabase_auth_service.get_service_credentials(db, principal.workspace_id)
        if not url or not key:
            return {"status": "skipped", "reason": "no_credentials"}
        ws = principal.workspace_id
        local_members = _member_ids(db, ws)
        upsert = _http_upsert(url, key)
        fetch = _http_fetch(url, key)
        prefetched_memberships, members = _discover_remote_members(
            db, fetch, ws, local_members
        )
        profile_fetch = _profile_fetch_with_missing(db, fetch)
        pulled = pushed = 0
        failures: list[str] = []
        for spec in SYNCED_TABLES:
            try:
                table_fetch = fetch
                if spec.user_scoped:
                    table_fetch = profile_fetch
                elif (
                    spec.table_name == "workspace_members"
                    and prefetched_memberships is not None
                ):
                    cached_rows = prefetched_memberships

                    def cached_member_fetch(*_args, **_kwargs) -> list[dict]:
                        return cached_rows

                    table_fetch = cached_member_fetch
                pulled += pull_table(
                    db, url, key, ws, members, spec, fetch=table_fetch
                )
                pushed += push_table(db, url, key, ws, members, spec, upsert=upsert)
            except Exception as exc:  # per-table isolation; keep going
                # A failed statement aborts the whole Postgres transaction. Without
                # this rollback the session stays poisoned and EVERY later table in
                # SYNCED_TABLES fails too — one bad row looked like a dead sync.
                db.rollback()
                failures.append(f"{spec.table_name}: {exc}")
                log.debug("sync skipped for %s: %s", spec.table_name, exc)
        if failures:
            # Visible signal: a missing Supabase schema makes EVERY table fail here,
            # which previously stayed silent at DEBUG and looked like a healthy sync.
            log.warning(
                "Supabase sync: %d/%d tables failed (first: %s)",
                len(failures), len(SYNCED_TABLES), failures[0][:300],
            )
        status = "ok" if not failures else "partial"
        return {
            "status": status,
            "pulled": pulled,
            "pushed": pushed,
            "tables": len(SYNCED_TABLES),
            "failed": len(failures),
        }
    except Exception as exc:
        log.debug("sync_two_way failed: %s", exc)
        return {"status": "error", "reason": str(exc)}
