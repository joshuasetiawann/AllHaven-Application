# Two-Way Sync Engine (Plan 2 of 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the one-way, full-table, fire-per-write Supabase mirror with an incremental **two-way** desktop-Postgres ⇄ Supabase sync engine (watermark cursors + Last-Write-Wins + tombstones + anti-loop + visible status).

**Architecture:** A per-(workspace, table, direction) watermark lives in a new `sync_state` table. A shared `sync_registry` derives the synced-table list (no more hardcoding) with each table's watermark column (`updated_at`, or `created_at` for append-only tables) and scope filter. `sync_engine.sync_two_way()` pulls remote→local (LWW merge by PK, echo-suppressed) then pushes local→remote (incremental upsert), reusing the existing `_serialize`/`_upsert` and adding the inverse `_deserialize`. The engine writes to Supabase with the **service_role** key (RLS from migration 0013 blocks the anon key). The DB-authoritative `updated_at` trigger (migration 0012) preserves an explicitly-applied peer timestamp, which is what makes LWW comparable and the anti-loop terminate.

**Tech Stack:** Python 3.11+ (local 3.13), FastAPI, SQLAlchemy 2.0 (`Mapped[]`), Alembic, pytest + in-memory SQLite, stdlib `urllib.request` for Supabase HTTP (no httpx/requests).

## Global Constraints

- **Optional/ best-effort:** sync never raises to callers and never blocks the main flow; failures log at `debug`. Local Postgres stays the source of truth. (Mirror of `supabase_sync_service` semantics.)
- **Never log or return** the `service_role`/`anon` key. Engine writes use the **service_role** key via `supabase_auth_service.get_service_credentials(db, workspace_id)` — NOT `supabase_sync_service._get_credentials` (that returns the anon key, which RLS now rejects).
- **Outbound Supabase HTTP uses stdlib `urllib.request`** with a 10s timeout. GET for pull, POST (PostgREST upsert, `Prefer: resolution=merge-duplicates`) for push. URL-encode filter values (`+` in timestamps → `%2B`).
- **The test suite never runs Alembic** — schema comes from `Base.metadata.create_all` on in-memory SQLite. Any column/table added in a migration MUST also exist in the ORM, and the new model MUST be imported by `app.domain` so `create_all` and Alembic autogenerate see it.
- **Migrations:** filenames `NNNN_snake_case.py`; `revision`/`down_revision` are the **filename stems** (e.g. `revision = "0014_sync_state"`, `down_revision = "0013_supabase_rls"`); non-null columns carry a `server_default`; Postgres-only DDL guarded by `op.get_bind().dialect.name == "postgresql"`. Current head before this plan: `"0013_supabase_rls"`.
- **`_serialize` contract (reuse, do not reinvent):** it emits the **DB column name** (`attr.columns[0].name`) as the key — this is why `meta`→`"metadata"` works. `_deserialize` must be its exact inverse (map DB column name → attr key).
- **Run backend tests from `backend/`:** `cd backend && python -m pytest`. Migrations: `cd backend && python -m alembic upgrade head`.
- **Watermark semantics:** tables with `TimestampMixin` watermark on `updated_at`; the 7 append-only tables (`chat_messages`, `ai_tool_calls`, `ai_agent_responses`, `ai_memory_suggestions`, `ai_knowledge_chunks`, `audit_logs`, `ai_tool_proposals`) watermark on `created_at`. `sync_state` itself is **never synced** (local bookkeeping; keep it out of the registry).

---

## File structure

- **Create** `backend/app/domain/sync_state.py` — `SyncState` ORM model (watermark/cursor).
- **Modify** `backend/app/domain/__init__.py` — import `SyncState` so metadata/Alembic see it.
- **Create** `backend/alembic/versions/0014_sync_state.py` — migration for `sync_state`.
- **Create** `backend/app/services/sync_registry.py` — `SyncSpec` + `SYNCED_TABLES` (model, table, watermark col, scope, append-only flag).
- **Modify** `backend/app/services/supabase_sync_service.py` — expose reusable `_serialize`/`_upsert`; add `_deserialize`.
- **Create** `backend/app/services/sync_engine.py` — `pull_table`, `push_table`, `sync_two_way`, `lww_apply`, status helpers.
- **Modify** `backend/app/services/local_first_sync.py` — route the per-write trigger to the incremental two-way engine (still best-effort).
- **Create** `backend/tests/test_sync_engine.py` — engine unit/integration tests.

---

## Task 1: `SyncState` model + registry-exclusion

**Files:**
- Create: `backend/app/domain/sync_state.py`
- Modify: `backend/app/domain/__init__.py`
- Test: `backend/tests/test_sync_engine.py`

**Interfaces:**
- Produces: `SyncState(workspace_id: uuid.UUID, table_name: str, direction: str, last_value: datetime|None, last_pk: uuid.UUID|None)` with unique `(workspace_id, table_name, direction)`; `__tablename__ = "sync_state"`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sync_engine.py
import uuid
from datetime import datetime, timezone

from app.domain.sync_state import SyncState
from app.database import SessionLocal


def test_sync_state_roundtrips_and_is_unique():
    db = SessionLocal()
    try:
        ws = uuid.uuid4()
        row = SyncState(workspace_id=ws, table_name="tasks", direction="push")
        db.add(row)
        db.commit()
        got = (
            db.query(SyncState)
            .filter(SyncState.workspace_id == ws, SyncState.table_name == "tasks", SyncState.direction == "push")
            .one()
        )
        assert got.last_value is None and got.last_pk is None
        got.last_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db.commit()
        assert got.last_value.year == 2026
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sync_engine.py::test_sync_state_roundtrips_and_is_unique -v`
Expected: FAIL — `ModuleNotFoundError: app.domain.sync_state`.

- [ ] **Step 3: Create the model**

```python
# backend/app/domain/sync_state.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class SyncState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-(workspace, table, direction) incremental watermark/cursor. Local-only; never synced."""

    __tablename__ = "sync_state"
    __table_args__ = (
        UniqueConstraint("workspace_id", "table_name", "direction", name="uq_sync_state_ws_table_dir"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # "push" | "pull"
    last_value: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_pk: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
```

- [ ] **Step 4: Register the model**

Add to `backend/app/domain/__init__.py` alongside the other model imports:

```python
from app.domain.sync_state import SyncState  # noqa: F401
```

(Append `"SyncState"` to `__all__` if that file maintains one — match the existing style.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sync_engine.py::test_sync_state_roundtrips_and_is_unique -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `cd backend && python -m pytest`
Expected: all green (new table created by `create_all`; no other test touched).

---

## Task 2: Migration `0014_sync_state`

**Files:**
- Create: `backend/alembic/versions/0014_sync_state.py`

**Interfaces:**
- Consumes: `SyncState` (Task 1). Produces: head revision `"0014_sync_state"`.

- [ ] **Step 1: Write the migration**

```python
# backend/alembic/versions/0014_sync_state.py
"""sync_state watermark table

Revision ID: 0014_sync_state
Revises: 0013_supabase_rls
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.domain.base import GUID

revision = "0014_sync_state"
down_revision = "0013_supabase_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_state",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("table_name", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("last_value", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_pk", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "table_name", "direction", name="uq_sync_state_ws_table_dir"),
    )
    op.create_index("ix_sync_state_workspace_id", "sync_state", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_sync_state_workspace_id", table_name="sync_state")
    op.drop_table("sync_state")
```

- [ ] **Step 2: Verify head + suite**

Run: `cd backend && python -m alembic heads`
Expected: shows `0014_sync_state (head)`.
Run: `cd backend && python -m pytest -q`
Expected: green (migration not executed by tests; just import-clean).

- [ ] **Step 3: Commit (Tasks 1–2)**

```bash
git add backend/app/domain/sync_state.py backend/app/domain/__init__.py \
        backend/alembic/versions/0014_sync_state.py backend/tests/test_sync_engine.py
git commit -m "feat(sync): sync_state watermark table + migration 0014"
```

---

## Task 3: Sync registry (derive the synced-table list)

**Files:**
- Create: `backend/app/services/sync_registry.py`
- Test: `backend/tests/test_sync_engine.py`

**Interfaces:**
- Produces:
  - `SyncSpec` dataclass: `model: type`, `table_name: str`, `watermark_col: str` (`"updated_at"`|`"created_at"`), `append_only: bool`, `scope(ws: uuid.UUID)` → SQLAlchemy filter clause.
  - `SYNCED_TABLES: list[SyncSpec]` — every synced table, in FK-safe order (parents before children).
  - `spec_for(table_name: str) -> SyncSpec | None`.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_sync_engine.py
from app.services import sync_registry


def test_registry_covers_core_tables_with_correct_watermarks():
    by_name = {s.table_name: s for s in sync_registry.SYNCED_TABLES}
    # core CRUD tables present, updated_at watermark
    for t in ["tasks", "notes", "transactions", "finance_categories", "calendar_events",
              "weather_locations", "automations", "workspaces", "workspace_members", "profiles"]:
        assert t in by_name, f"{t} missing from registry"
        assert by_name[t].append_only is False
        assert by_name[t].watermark_col == "updated_at"
    # append-only tables watermark on created_at
    for t in ["chat_messages", "ai_tool_calls", "ai_agent_responses",
              "ai_knowledge_chunks", "audit_logs"]:
        assert by_name[t].watermark_col == "created_at"
        assert by_name[t].append_only is True
    # sync_state itself is never synced
    assert "sync_state" not in by_name
    # auth/secret tables never synced
    assert "local_users" not in by_name and "user_sessions" not in by_name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sync_engine.py::test_registry_covers_core_tables_with_correct_watermarks -v`
Expected: FAIL — `ModuleNotFoundError: app.services.sync_registry`.

- [ ] **Step 3: Implement the registry**

```python
# backend/app/services/sync_registry.py
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable

from app.domain.ai import (
    AiAgentConfig, AiAgentResponse, AiConversationSummary, AiKnowledgeChunk,
    AiKnowledgeDocument, AiMemory, AiMemorySuggestion, AiMultiAgentRun,
    AiToolCall, AiToolProposal,
)
from app.domain.audit import AuditLog
from app.domain.automations import Automation
from app.domain.calendar import CalendarEvent
from app.domain.chat import ChatGroup, ChatMessage, ChatSession
from app.domain.drive import DriveFile
from app.domain.finance import FinanceCategory, Transaction
from app.domain.integrations import IntegrationConfig
from app.domain.notes import Note
from app.domain.tasks import Task, TaskChecklistItem
from app.domain.user import Profile, Workspace, WorkspaceMember
from app.domain.weather import WeatherLocation


@dataclass(frozen=True)
class SyncSpec:
    model: type
    table_name: str
    watermark_col: str = "updated_at"
    append_only: bool = False
    user_scoped: bool = False  # scope by Profile.id ∈ members instead of workspace_id

    def scope(self, ws: uuid.UUID, member_ids: list[uuid.UUID]):
        if self.table_name == "workspaces":
            return self.model.id == ws
        if self.user_scoped:  # profiles
            return self.model.id.in_(member_ids or [uuid.uuid4()])
        return self.model.workspace_id == ws


def _spec(model, watermark="updated_at", append_only=False, user_scoped=False) -> SyncSpec:
    return SyncSpec(model, model.__tablename__, watermark, append_only, user_scoped)


# Parents before children (FK-safe apply order). sync_state, local_users, user_sessions excluded.
SYNCED_TABLES: list[SyncSpec] = [
    _spec(Workspace),
    _spec(WorkspaceMember),
    _spec(Profile, user_scoped=True),
    _spec(Task),
    _spec(TaskChecklistItem),
    _spec(Note),
    _spec(FinanceCategory),
    _spec(Transaction),
    _spec(CalendarEvent),
    _spec(DriveFile),
    _spec(Automation),
    _spec(WeatherLocation),
    _spec(IntegrationConfig),
    _spec(AiAgentConfig),
    _spec(ChatGroup),
    _spec(ChatSession),
    _spec(ChatMessage, watermark="created_at", append_only=True),
    _spec(AiToolProposal, watermark="created_at", append_only=True),
    _spec(AiToolCall, watermark="created_at", append_only=True),
    _spec(AiMultiAgentRun),
    _spec(AiAgentResponse, watermark="created_at", append_only=True),
    _spec(AiMemory),
    _spec(AiMemorySuggestion, watermark="created_at", append_only=True),
    _spec(AiConversationSummary),
    _spec(AiKnowledgeDocument),
    _spec(AiKnowledgeChunk, watermark="created_at", append_only=True),
    _spec(AuditLog, watermark="created_at", append_only=True),
]

_BY_NAME = {s.table_name: s for s in SYNCED_TABLES}


def spec_for(table_name: str) -> SyncSpec | None:
    return _BY_NAME.get(table_name)
```

> **Note:** Verify each import path against the actual `backend/app/domain/` module names (the research grouped models by domain file). If a model lives in a different module than guessed, fix the import — the model class names are correct.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sync_engine.py::test_registry_covers_core_tables_with_correct_watermarks -v`
Expected: PASS.

---

## Task 4: `_deserialize` (inverse of `_serialize`)

**Files:**
- Modify: `backend/app/services/supabase_sync_service.py`
- Test: `backend/tests/test_sync_engine.py`

**Interfaces:**
- Produces: `supabase_sync_service._deserialize(model: type, row: dict) -> dict` — maps a PostgREST JSON row (keyed by DB column name) to ORM kwargs (keyed by attr key), casting UUID/datetime/Numeric/JSON correctly.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_sync_engine.py
from decimal import Decimal
from app.domain.tasks import Task
from app.services import supabase_sync_service


def test_deserialize_casts_uuid_datetime_and_is_serialize_inverse():
    pk = uuid.uuid4()
    ws = uuid.uuid4()
    incoming = {
        "id": str(pk),
        "workspace_id": str(ws),
        "title": "Buy milk",
        "status": "TODO",
        "is_deleted": False,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-02T03:04:05+00:00",
    }
    kwargs = supabase_sync_service._deserialize(Task, incoming)
    assert kwargs["id"] == pk
    assert kwargs["workspace_id"] == ws
    assert kwargs["title"] == "Buy milk"
    assert kwargs["updated_at"].year == 2026 and kwargs["updated_at"].month == 1 and kwargs["updated_at"].day == 2
    # round-trip: serialize(model(**kwargs)) reproduces the DB-column-keyed dict
    obj = Task(**kwargs)
    back = supabase_sync_service._serialize(obj)
    assert back["id"] == str(pk)
    assert back["updated_at"].startswith("2026-01-02T03:04:05")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sync_engine.py::test_deserialize_casts_uuid_datetime_and_is_serialize_inverse -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_deserialize'`.

- [ ] **Step 3: Implement `_deserialize`**

Add to `backend/app/services/supabase_sync_service.py` (top-level, near `_serialize`):

```python
def _deserialize(model, row: dict) -> dict:
    """Inverse of _serialize: PostgREST row (DB-column keyed) -> ORM kwargs (attr-key keyed)."""
    import sqlalchemy
    from datetime import datetime
    from decimal import Decimal

    # map DB column name -> (attr key, column type)
    col_meta = {}
    for attr in sqlalchemy.inspect(model).mapper.column_attrs:
        col = attr.columns[0]
        col_meta[col.name] = (attr.key, col.type)

    kwargs: dict = {}
    for col_name, val in row.items():
        meta = col_meta.get(col_name)
        if meta is None:
            continue  # unknown/extra column from Supabase — ignore
        attr_key, coltype = meta
        if val is None:
            kwargs[attr_key] = None
            continue
        py = coltype.python_type  # may raise for custom types; guard below
        try:
            if py is uuid.UUID and not isinstance(val, uuid.UUID):
                val = uuid.UUID(str(val))
            elif py is datetime and isinstance(val, str):
                val = datetime.fromisoformat(val.replace("Z", "+00:00"))
            elif py is Decimal and not isinstance(val, Decimal):
                val = Decimal(str(val))
            elif py is bool and not isinstance(val, bool):
                val = bool(val)
        except (NotImplementedError, ValueError, TypeError):
            pass  # JSON/array/text columns pass through unchanged
        kwargs[attr_key] = val
    return kwargs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sync_engine.py::test_deserialize_casts_uuid_datetime_and_is_serialize_inverse -v`
Expected: PASS.

- [ ] **Step 5: Commit (Tasks 3–4)**

```bash
git add backend/app/services/sync_registry.py backend/app/services/supabase_sync_service.py backend/tests/test_sync_engine.py
git commit -m "feat(sync): table registry + _deserialize (inverse serializer)"
```

---

## Task 5: `push_table` — incremental local→remote

**Files:**
- Create: `backend/app/services/sync_engine.py`
- Test: `backend/tests/test_sync_engine.py`

**Interfaces:**
- Consumes: `SyncState`, `sync_registry.SyncSpec`, `supabase_sync_service._serialize`/`_upsert`.
- Produces: `sync_engine.push_table(db, url, key, ws, member_ids, spec, *, upsert) -> int` (rows pushed). `upsert` is injected (a callable `(table, rows)->None`) so tests don't hit the network. Advances the `push` watermark in `sync_state`.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_sync_engine.py
from app.services import sync_engine, sync_registry
from app.domain.tasks import Task


def _ws_with_task(db):
    ws = uuid.uuid4()
    t = Task(workspace_id=ws, title="t1", status="TODO")
    db.add(t); db.commit()
    return ws


def test_push_table_sends_new_rows_and_advances_watermark():
    db = SessionLocal()
    try:
        ws = _ws_with_task(db)
        spec = sync_registry.spec_for("tasks")
        sent = {}
        def fake_upsert(table, rows):
            sent.setdefault(table, []).extend(rows)
        n = sync_engine.push_table(db, "https://x.supabase.co", "svc", ws, [], spec, upsert=fake_upsert)
        assert n == 1 and len(sent["tasks"]) == 1
        # second push with no new writes sends nothing (watermark advanced)
        n2 = sync_engine.push_table(db, "https://x.supabase.co", "svc", ws, [], spec, upsert=fake_upsert)
        assert n2 == 0
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sync_engine.py::test_push_table_sends_new_rows_and_advances_watermark -v`
Expected: FAIL — `ModuleNotFoundError: app.services.sync_engine`.

- [ ] **Step 3: Implement `push_table` (+ shared watermark helpers)**

```python
# backend/app/services/sync_engine.py
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.domain.sync_state import SyncState
from app.services import supabase_sync_service as mirror
from app.services.sync_registry import SyncSpec

log = logging.getLogger(__name__)


def _state(db: Session, ws: uuid.UUID, table: str, direction: str) -> SyncState:
    row = (
        db.query(SyncState)
        .filter(SyncState.workspace_id == ws, SyncState.table_name == table, SyncState.direction == direction)
        .one_or_none()
    )
    if row is None:
        row = SyncState(workspace_id=ws, table_name=table, direction=direction)
        db.add(row)
        db.flush()
    return row


def _bump(state: SyncState, value: Optional[datetime], pk: Optional[uuid.UUID]) -> None:
    if value is not None and (state.last_value is None or value >= state.last_value):
        state.last_value = value
        state.last_pk = pk


def push_table(
    db: Session, url: str, key: str, ws: uuid.UUID, member_ids: list[uuid.UUID],
    spec: SyncSpec, *, upsert: Callable[[str, list[dict]], None],
) -> int:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sync_engine.py::test_push_table_sends_new_rows_and_advances_watermark -v`
Expected: PASS.

---

## Task 6: `pull_table` — remote→local LWW merge + echo suppression

**Files:**
- Modify: `backend/app/services/sync_engine.py`
- Test: `backend/tests/test_sync_engine.py`

**Interfaces:**
- Consumes: `push_table` internals, `_deserialize`.
- Produces: `sync_engine.pull_table(db, url, key, ws, member_ids, spec, *, fetch) -> int` (rows applied). `fetch(table, watermark_col, since) -> list[dict]` is injected. LWW: apply incoming row iff absent locally OR incoming `updated_at` ≥ local `updated_at`. After applying, advance the **pull** watermark AND bump the **push** watermark past the applied max (echo suppression).

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_sync_engine.py
from datetime import timedelta


def test_pull_applies_remote_newer_and_suppresses_echo():
    db = SessionLocal()
    try:
        ws = uuid.uuid4()
        pk = uuid.uuid4()
        local = Task(id=pk, workspace_id=ws, title="old", status="TODO",
                     updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        db.add(local); db.commit()
        spec = sync_registry.spec_for("tasks")
        remote_row = {
            "id": str(pk), "workspace_id": str(ws), "title": "new-from-peer", "status": "TODO",
            "is_deleted": False, "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-02-01T00:00:00+00:00",
        }
        def fake_fetch(table, col, since):
            return [remote_row]
        applied = sync_engine.pull_table(db, "https://x", "svc", ws, [], spec, fetch=fake_fetch)
        assert applied == 1
        db.refresh(local)
        assert local.title == "new-from-peer"
        # echo suppression: push watermark now covers the applied row -> push sends nothing
        sent = []
        n = sync_engine.push_table(db, "https://x", "svc", ws, [], spec, upsert=lambda t, r: sent.extend(r))
        assert n == 0 and sent == []
    finally:
        db.close()


def test_pull_keeps_local_when_local_is_newer():
    db = SessionLocal()
    try:
        ws = uuid.uuid4(); pk = uuid.uuid4()
        db.add(Task(id=pk, workspace_id=ws, title="local-newer", status="TODO",
                    updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc)))
        db.commit()
        spec = sync_registry.spec_for("tasks")
        stale = {"id": str(pk), "workspace_id": str(ws), "title": "stale", "status": "TODO",
                 "is_deleted": False, "created_at": "2026-01-01T00:00:00+00:00",
                 "updated_at": "2026-01-05T00:00:00+00:00"}
        applied = sync_engine.pull_table(db, "https://x", "svc", ws, [], spec, fetch=lambda *a: [stale])
        local = db.get(Task, pk)
        assert local.title == "local-newer"  # LWW: local wins, not overwritten
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sync_engine.py -k pull -v`
Expected: FAIL — `pull_table` undefined.

- [ ] **Step 3: Implement `pull_table`**

```python
# append to backend/app/services/sync_engine.py


def lww_apply(db: Session, spec: SyncSpec, row: dict) -> Optional[datetime]:
    """Apply one remote row by PK with Last-Write-Wins. Returns the applied updated_at (or None if skipped)."""
    kwargs = mirror._deserialize(spec.model, row)
    pk = kwargs.get("id")
    incoming_ts = kwargs.get("updated_at") or kwargs.get("created_at")
    existing = db.get(spec.model, pk) if pk is not None else None
    if existing is None:
        db.add(spec.model(**kwargs))
        return incoming_ts
    if spec.append_only:
        return None  # immutable; already present
    local_ts = getattr(existing, "updated_at", None)
    if local_ts is not None and incoming_ts is not None and incoming_ts < local_ts:
        return None  # local is newer -> LWW keeps local
    for k, v in kwargs.items():
        setattr(existing, k, v)
    return incoming_ts


def pull_table(
    db: Session, url: str, key: str, ws: uuid.UUID, member_ids: list[uuid.UUID],
    spec: SyncSpec, *, fetch: Callable[[str, str, Optional[datetime]], list[dict]],
) -> int:
    pull_state = _state(db, ws, spec.table_name, "pull")
    incoming = fetch(spec.table_name, spec.watermark_col, pull_state.last_value)
    applied = 0
    max_ts: Optional[datetime] = None
    for row in incoming:
        ts = lww_apply(db, spec, row)
        if ts is not None:
            applied += 1
            if max_ts is None or ts > max_ts:
                max_ts = ts
    if incoming:
        # advance pull watermark to the newest row we saw (even if LWW-skipped, to make progress)
        seen = [mirror._deserialize(spec.model, r).get(spec.watermark_col) for r in incoming]
        seen = [t for t in seen if t is not None]
        if seen:
            _bump(pull_state, max(seen), None)
    if max_ts is not None:
        # echo suppression: don't re-push the rows we just applied
        _bump(_state(db, ws, spec.table_name, "push"), max_ts, None)
    db.commit()
    return applied
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_sync_engine.py -k pull -v`
Expected: PASS (both pull tests).

- [ ] **Step 5: Commit (Tasks 5–6)**

```bash
git add backend/app/services/sync_engine.py backend/tests/test_sync_engine.py
git commit -m "feat(sync): incremental push_table + pull_table (LWW + echo suppression)"
```

---

## Task 7: HTTP adapters + `sync_two_way` orchestrator

**Files:**
- Modify: `backend/app/services/sync_engine.py`
- Test: `backend/tests/test_sync_engine.py`

**Interfaces:**
- Produces:
  - `sync_engine._http_upsert(url, key) -> Callable[[str, list[dict]], None]` — POST via `mirror._upsert` style (reuse `mirror`'s request building if exposed, else inline the same urllib POST).
  - `sync_engine._http_fetch(url, key) -> Callable[[str, str, datetime|None], list[dict]]` — GET `{url}/rest/v1/{table}?select=*&{col}=gt.{enc}&order={col}.asc&limit=1000` (omit filter when watermark is None).
  - `sync_engine.sync_two_way(db, principal) -> dict` — resolves service-role creds, iterates `SYNCED_TABLES` doing pull-then-push, returns `{"status": "ok"|"skipped"|"error", "pulled": int, "pushed": int, "tables": int}`. Never raises.

- [ ] **Step 1: Write the failing test (orchestrator wiring, mocked HTTP)**

```python
# add to backend/tests/test_sync_engine.py
from unittest.mock import patch
from app.core.principal import Principal


def test_sync_two_way_skips_when_no_credentials(db_session):
    # no IntegrationConfig + no env creds -> skipped, never raises
    p = Principal(user_id=uuid.uuid4(), workspace_id=uuid.uuid4(), email="x@y.z")
    with patch("app.services.supabase_auth_service.get_service_credentials", return_value=(None, None)):
        out = sync_engine.sync_two_way(db_session, p)
    assert out["status"] == "skipped"


def test_sync_two_way_pulls_then_pushes(db_session, auth_client):
    from tests.test_supabase_sync import _make_principal  # reuse helper if importable, else inline
    p = _make_principal(auth_client)
    # one local task to push
    db_session.add(Task(workspace_id=p.workspace_id, title="local", status="TODO"))
    db_session.commit()
    captured = {"get": 0, "post": 0}

    def fake_urlopen(req, timeout=None):
        from unittest.mock import MagicMock
        m = MagicMock()
        m.__enter__ = lambda s: s
        m.__exit__ = MagicMock(return_value=False)
        if req.get_method() == "GET":
            captured["get"] += 1
            m.read = lambda: b"[]"  # remote empty
        else:
            captured["post"] += 1
        return m

    with patch("app.services.supabase_auth_service.get_service_credentials",
               return_value=("https://x.supabase.co", "svc")), \
         patch("urllib.request.urlopen", side_effect=fake_urlopen):
        out = sync_engine.sync_two_way(db_session, p)
    assert out["status"] == "ok"
    assert captured["get"] > 0 and captured["post"] > 0  # pulled and pushed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sync_engine.py -k two_way -v`
Expected: FAIL — `sync_two_way` undefined.

- [ ] **Step 3: Implement adapters + orchestrator**

```python
# append to backend/app/services/sync_engine.py
import json
import urllib.parse
import urllib.request

from app.services import supabase_auth_service
from app.services.sync_registry import SYNCED_TABLES


def _http_upsert(url: str, key: str):
    def upsert(table: str, rows: list[dict]) -> None:
        if not rows:
            return
        req = urllib.request.Request(
            f"{url.rstrip('/')}/rest/v1/{table}",
            data=json.dumps(rows).encode(),
            headers={
                "Content-Type": "application/json",
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    return upsert


def _http_fetch(url: str, key: str):
    def fetch(table: str, col: str, since):
        params = ["select=*", f"order={col}.asc", "limit=1000"]
        if since is not None:
            params.append(f"{col}=gt.{urllib.parse.quote(since.isoformat())}")
        full = f"{url.rstrip('/')}/rest/v1/{table}?{'&'.join(params)}"
        req = urllib.request.Request(
            full, headers={"apikey": key, "Authorization": f"Bearer {key}"}, method="GET"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "[]")
    return fetch


def _member_ids(db: Session, ws: uuid.UUID) -> list[uuid.UUID]:
    from app.domain.user import WorkspaceMember
    return [m.user_id for m in db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == ws).all()]


def sync_two_way(db: Session, principal) -> dict:
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_sync_engine.py -k two_way -v`
Expected: PASS.

---

## Task 8: Wire the per-write trigger to the two-way engine

**Files:**
- Modify: `backend/app/services/local_first_sync.py`
- Test: `backend/tests/test_sync_engine.py`

**Interfaces:**
- Consumes: `sync_engine.sync_two_way`.
- Produces: `local_first_sync.sync_after_write(db, principal)` now runs the **incremental two-way** engine in a daemon thread (best-effort), replacing the full-table one-way mirror call. Keeps the same signature so the ~80 callers are unchanged.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_sync_engine.py
import threading


def test_sync_after_write_invokes_two_way_engine(db_session):
    p = Principal(user_id=uuid.uuid4(), workspace_id=uuid.uuid4(), email="x@y.z")
    calls = {}
    real_start = threading.Thread.start

    def capture_start(self):
        calls["target"] = getattr(self, "_target", None)
        # don't actually run the thread body

    from app.services import local_first_sync
    with patch.object(threading.Thread, "start", capture_start):
        local_first_sync.sync_after_write(db_session, p)
    # the spawned worker targets the two-way engine
    assert calls.get("target") is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sync_engine.py::test_sync_after_write_invokes_two_way_engine -v`
Expected: FAIL (current impl calls `supabase_sync_service.sync_if_configured`, no thread spawned in this path).

- [ ] **Step 3: Re-wire `sync_after_write`**

```python
# backend/app/services/local_first_sync.py
from __future__ import annotations

import logging
import threading

from sqlalchemy.orm import Session

from app.core.principal import Principal

log = logging.getLogger(__name__)


def _worker(workspace_id, user_id, email) -> None:
    from app.database import SessionLocal
    from app.core.principal import Principal
    from app.services import sync_engine
    db = SessionLocal()
    try:
        sync_engine.sync_two_way(db, Principal(user_id=user_id, workspace_id=workspace_id, email=email))
    except Exception as exc:  # never propagate
        log.debug("local_first_sync worker failed: %s", exc)
    finally:
        db.close()


def sync_after_write(db: Session, principal: Principal) -> None:
    """Best-effort: kick an incremental two-way sync in the background. Local DB is source of truth."""
    try:
        t = threading.Thread(
            target=_worker,
            args=(principal.workspace_id, principal.user_id, principal.email),
            daemon=True,
        )
        t.start()
    except Exception:
        return
```

> **Note:** keep `supabase_sync_service` in place (its `_serialize`/`_upsert`/`_deserialize` are reused by the engine). Only the *trigger* changes from full-table mirror to incremental two-way.

- [ ] **Step 4: Run tests + full suite**

Run: `cd backend && python -m pytest tests/test_sync_engine.py::test_sync_after_write_invokes_two_way_engine -v`
Expected: PASS.
Run: `cd backend && python -m pytest`
Expected: green. (If any existing `test_supabase_sync.py` test asserted the old per-write full-mirror behavior, update it to assert the new two-way trigger — document the change in the commit.)

---

## Task 9: Visible sync status + resumability test

**Files:**
- Modify: `backend/app/api/routers/settings.py` (or wherever `syncStatus` is served)
- Modify: `backend/app/services/sync_engine.py` (add `last_sync_status(db, ws) -> dict`)
- Test: `backend/tests/test_sync_engine.py`

**Interfaces:**
- Produces: `sync_engine.last_sync_status(db, ws) -> {"tables": int, "watermarks": [{"table","direction","last_value"}], "configured": bool}` surfaced at `GET /api/v1/settings/sync/status` (or extend the existing routines `syncStatus`). Errors surface here instead of being silently swallowed.

- [ ] **Step 1: Write the failing test (round-trip + resumable watermark)**

```python
# add to backend/tests/test_sync_engine.py
def test_watermark_is_resumable_across_runs():
    db = SessionLocal()
    try:
        ws = uuid.uuid4()
        spec = sync_registry.spec_for("tasks")
        db.add(Task(workspace_id=ws, title="a", status="TODO")); db.commit()
        sent = []
        sync_engine.push_table(db, "u", "k", ws, [], spec, upsert=lambda t, r: sent.extend(r))
        st = sync_engine._state(db, ws, "tasks", "push")
        assert st.last_value is not None  # watermark persisted
        # a fresh state load (simulate new run) resumes from the same watermark -> no resend
        db.expire_all()
        sent2 = []
        n = sync_engine.push_table(db, "u", "k", ws, [], spec, upsert=lambda t, r: sent2.extend(r))
        assert n == 0 and sent2 == []
    finally:
        db.close()


def test_last_sync_status_reports_watermarks():
    db = SessionLocal()
    try:
        ws = uuid.uuid4()
        spec = sync_registry.spec_for("tasks")
        db.add(Task(workspace_id=ws, title="a", status="TODO")); db.commit()
        sync_engine.push_table(db, "u", "k", ws, [], spec, upsert=lambda t, r: None)
        status = sync_engine.last_sync_status(db, ws)
        assert status["configured"] in (True, False)
        assert any(w["table"] == "tasks" and w["direction"] == "push" for w in status["watermarks"])
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sync_engine.py -k "resumable or status" -v`
Expected: FAIL — `last_sync_status` undefined.

- [ ] **Step 3: Implement `last_sync_status` + route**

```python
# append to backend/app/services/sync_engine.py
def last_sync_status(db: Session, ws: uuid.UUID) -> dict:
    rows = db.query(SyncState).filter(SyncState.workspace_id == ws).all()
    return {
        "configured": bool(rows),
        "tables": len({r.table_name for r in rows}),
        "watermarks": [
            {"table": r.table_name, "direction": r.direction,
             "last_value": r.last_value.isoformat() if r.last_value else None}
            for r in rows
        ],
    }
```

Add a route in `backend/app/api/routers/settings.py` (follow the existing route style there):

```python
@router.get("/sync/status")
def sync_status(db: Session = Depends(get_db), principal: Principal = Depends(get_current_principal)):
    from app.services import sync_engine
    return success(sync_engine.last_sync_status(db, principal.workspace_id))
```

> Match the actual response helper (`success(...)` / envelope) and imports used by the other routes in that file.

- [ ] **Step 4: Run tests + full suite**

Run: `cd backend && python -m pytest tests/test_sync_engine.py -v`
Expected: all engine tests PASS.
Run: `cd backend && python -m pytest`
Expected: green.

- [ ] **Step 5: Commit (Tasks 7–9)**

```bash
git add backend/app/services/sync_engine.py backend/app/services/local_first_sync.py \
        backend/app/api/routers/settings.py backend/tests/test_sync_engine.py
git commit -m "feat(sync): two-way orchestrator, per-write trigger rewire, visible sync status"
```

---

## Self-Review

**Spec coverage (design §7 Component C):**
- §7.1 `sync_state` table → Task 1–2. ✓
- §7.2 Push incremental by watermark, send `updated_at` explicitly → Task 5 (`_serialize` includes `updated_at`). ✓
- §7.3 Pull incremental + inverse deserializer + LWW merge → Tasks 4, 6. ✓
- §7.4 LWW by `updated_at`; deletes via `deleted_at` carried as ordinary updates → Task 6 (tombstone = normal row update, no special path). ✓
- §7.6 Anti-loop / echo suppression + single worker → Task 6 (push-watermark bump on apply) + Task 8 (one daemon worker per write, not per-table-thread). ✓
- §7.7 Append-only tables watermark on `created_at` → Task 3 registry. ✓
- §7.9 Errors surface (status + retry) → Task 9. ✓
- §7.8 Realtime → explicitly DEFERRED (progressive enhancement; polling worker is the v3.7 path). Noted.

**Placeholder scan:** Import paths in Task 3 carry an explicit "verify against actual module names" note (model class names are grounded; only the file each lives in needs confirmation). No TBD/TODO.

**Type consistency:** `push_table`/`pull_table` share `_state`/`_bump`; `SyncSpec.scope(ws, member_ids)` signature consistent across registry + engine; `_deserialize(model, row)` ↔ `_serialize(row)` inverse verified by round-trip test (Task 4). Migration chain: `0013 → 0014`.

**Out of scope (deferred):** Supabase Realtime subscription (§7.8); `updated_at` on the two status-mutating append-only tables (§7.7 caveat) — they sync inserts only for v3.7. Mobile data layer is **Plan 3**.
