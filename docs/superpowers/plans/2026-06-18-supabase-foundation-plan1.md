# Supabase Foundation (Plan 1 of 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Supabase database (schema + RLS + authoritative `updated_at` triggers) and provision a Supabase Auth user for each AllHaven user, so Plan 2 (two-way sync) and Plan 3 (mobile-on-Supabase) have a foundation to build on.

**Architecture:** Reuse the existing portable Alembic migrations to build the identical schema on Supabase. Add additive columns (`deleted_at`, `profiles.supabase_user_id`), a Postgres-only `updated_at` trigger (runs on local Postgres + Supabase, no-ops on the SQLite test DB), and a Supabase-only RLS migration guarded by an env var so a local `alembic upgrade head` records but skips it. Provision Supabase Auth users best-effort via a new `supabase_auth_service` (stdlib `urllib`, GoTrue admin API), storing the returned Supabase id on the profile for RLS mapping.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0 (declarative `Mapped[]`), Alembic, pydantic-settings, pytest + in-memory SQLite, stdlib `urllib.request` for Supabase HTTP. Frontend: Next.js, TypeScript, `frontend/lib/api.ts` client.

## Global Constraints

- **Optional integrations never block the main flow and never raise to callers.** Provisioning is best-effort: failures log at `debug`, local registration still succeeds when Supabase is down/unconfigured. (`supabase_sync_service.py` docstring.)
- **Never log or return the `service_role` key or the user password** in any log line, exception message, or API response.
- **Admin (GoTrue) calls use the `service_role` key** for BOTH the `apikey` header and `Authorization: Bearer`. Never the anon key.
- **Do NOT reuse `supabase_sync_service._get_credentials`** for admin calls — it returns the anon key. Write a dedicated service-role resolver.
- **Outbound Supabase HTTP uses stdlib `urllib.request`** with a 10s timeout, matching `supabase_sync_service._do_sync`. Do not add httpx/requests.
- **The test suite never runs Alembic** — schema comes from `Base.metadata.create_all` on in-memory SQLite. Any column added in a migration MUST also be added to the ORM model, or tests won't see it.
- **Migrations:** filenames `NNNN_snake_case.py`; `down_revision` is the predecessor's **revision string** (not filename); non-null columns always carry a `server_default`; Postgres-only DDL guarded by `op.get_bind().dialect.name == "postgresql"`.
- **SQLAlchemy typing:** `from __future__ import annotations` at top; columns `name: Mapped[type] = mapped_column(...)`; nullable timestamps `Mapped[datetime | None]` with `DateTime(timezone=True)`.
- **Run backend tests from `backend/`:** `cd backend && python -m pytest`. Run migrations from `backend/`: `python -m alembic upgrade head`.

---

## File structure

- `backend/app/domain/*.py` — add `deleted_at` to the 10 soft-delete models; add `supabase_user_id` to `Profile`.
- `backend/alembic/versions/0010_soft_delete_deleted_at.py` — new, additive columns.
- `backend/alembic/versions/0011_profile_supabase_link.py` — new, `profiles.supabase_user_id`.
- `backend/alembic/versions/0012_updated_at_trigger.py` — new, Postgres-only trigger.
- `backend/alembic/versions/0013_supabase_rls.py` — new, Supabase-only (env-guarded) RLS + helpers.
- `backend/app/services/supabase_auth_service.py` — new, GoTrue admin provisioning + service-role resolver.
- `backend/app/services/auth_service.py` — wire provisioning into `register_user`.
- `backend/app/schemas/integrations.py` — add `SupabaseConnectRequest`.
- `backend/app/api/routers/settings.py` — add `POST /settings/supabase/connect`.
- `frontend/lib/api.ts` — add `settingsApi.connectSupabase`.
- `frontend/components/settings/IntegrationConfigModal.tsx` (or a new card) — "Connect to Supabase" control.
- `.env.example` — document `ALLHAVEN_DB_TARGET`.
- New test files under `backend/tests/`.

---

## Task 1: Add `deleted_at` to the soft-delete ORM models

**Files:**
- Modify: `backend/app/domain/tasks.py` (Task `:32`, TaskChecklistItem `:57`), `notes.py:25`, `finance.py` (FinanceCategory `:32`, Transaction `:53`), `calendar.py:36`, `files.py:29`, `integrations.py` (IntegrationConfig `:44`, AiAgentConfig `:73`), `automations.py:31`
- Test: `backend/tests/test_soft_delete_column.py`

**Interfaces:**
- Produces: a nullable `deleted_at: Mapped[datetime | None]` column (TIMESTAMPTZ) on all 10 soft-delete tables, alongside the existing `is_deleted` boolean. Used by Plan 2 to LWW-order deletes.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_soft_delete_column.py
"""Every soft-delete table carries a nullable deleted_at TIMESTAMPTZ column."""
from __future__ import annotations

from sqlalchemy import inspect

from app.core.database import engine

SOFT_DELETE_TABLES = [
    "tasks",
    "task_checklist_items",
    "notes",
    "finance_categories",
    "transactions",
    "calendar_events",
    "drive_files",
    "integration_configs",
    "ai_agent_configs",
    "automations",
]


def test_soft_delete_tables_have_deleted_at():
    inspector = inspect(engine)
    for table in SOFT_DELETE_TABLES:
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        assert "deleted_at" in cols, f"{table} missing deleted_at"
        assert cols["deleted_at"]["nullable"] is True, f"{table}.deleted_at must be nullable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_soft_delete_column.py -v`
Expected: FAIL — `AssertionError: tasks missing deleted_at`.

- [ ] **Step 3: Add the column to each model**

In each model class, immediately after its existing `is_deleted` line, add (the import `from datetime import datetime` and `DateTime` from sqlalchemy already exist in these files — verify and add if missing):

```python
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Apply to: `Task`, `TaskChecklistItem` (tasks.py), `Note` (notes.py), `FinanceCategory`, `Transaction` (finance.py), `CalendarEvent` (calendar.py), `DriveFile` (files.py), `IntegrationConfig`, `AiAgentConfig` (integrations.py), `Automation` (automations.py).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_soft_delete_column.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `cd backend && python -m pytest -q`
Expected: all pass (the new column is nullable and unused by existing code).

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain backend/tests/test_soft_delete_column.py
git commit -m "feat(db): add nullable deleted_at to soft-delete models (LWW tombstones)"
```

---

## Task 2: Alembic migration for `deleted_at`

**Files:**
- Create: `backend/alembic/versions/0010_soft_delete_deleted_at.py`

**Interfaces:**
- Consumes: migration head `0009_routine_preferences`.
- Produces: revision `0010_soft_delete_deleted_at` adding `deleted_at` to the 10 tables on a real Postgres DB. (Tests use SQLite via `create_all`, so this migration is verified by reading, not by the test suite — see Global Constraints.)

- [ ] **Step 1: Write the migration**

```python
# backend/alembic/versions/0010_soft_delete_deleted_at.py
"""soft-delete deleted_at timestamps

Revision ID: 0010_soft_delete_deleted_at
Revises: 0009_routine_preferences
Create Date: 2026-06-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_soft_delete_deleted_at"
down_revision: Union[str, None] = "0009_routine_preferences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = [
    "tasks",
    "task_checklist_items",
    "notes",
    "finance_categories",
    "transactions",
    "calendar_events",
    "drive_files",
    "integration_configs",
    "ai_agent_configs",
    "automations",
]


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, "deleted_at")
```

- [ ] **Step 2: Verify the migration imports and is the new head**

Run: `cd backend && python -m alembic heads`
Expected: a single head `0010_soft_delete_deleted_at (head)`.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/0010_soft_delete_deleted_at.py
git commit -m "feat(db): migration 0010 add deleted_at columns"
```

---

## Task 3: Add `profiles.supabase_user_id` (identity mapping) + migration

**Files:**
- Modify: `backend/app/domain/users.py` (Profile, `:26-33`)
- Create: `backend/alembic/versions/0011_profile_supabase_link.py`
- Test: `backend/tests/test_profile_supabase_link.py`

**Interfaces:**
- Produces: `Profile.supabase_user_id: Mapped[uuid.UUID | None]` (nullable, unique). Maps the app user → the Supabase Auth user id. Consumed by Task 6/7 (provisioning stores it) and the RLS `app_user_id()` helper (Task 5/0013).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_profile_supabase_link.py
"""Profile carries a nullable supabase_user_id mapping column."""
from __future__ import annotations

from sqlalchemy import inspect

from app.core.database import engine


def test_profile_has_supabase_user_id():
    cols = {c["name"]: c for c in inspect(engine).get_columns("profiles")}
    assert "supabase_user_id" in cols
    assert cols["supabase_user_id"]["nullable"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_profile_supabase_link.py -v`
Expected: FAIL — `KeyError`/assert on missing column.

- [ ] **Step 3: Add the column to Profile**

In `backend/app/domain/users.py`, inside `class Profile`, add (the `GUID` type is defined in `app.domain.base`; import it the way the file already imports base types — check the existing import line and extend it):

```python
    supabase_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), unique=True, nullable=True, index=True
    )
```

If `GUID` / `uuid` are not yet imported in `users.py`, add `import uuid` and add `GUID` to the existing `from app.domain.base import ...` line.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_profile_supabase_link.py -v`
Expected: PASS.

- [ ] **Step 5: Write the migration**

```python
# backend/alembic/versions/0011_profile_supabase_link.py
"""profiles.supabase_user_id mapping to Supabase Auth

Revision ID: 0011_profile_supabase_link
Revises: 0010_soft_delete_deleted_at
Create Date: 2026-06-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from app.domain.base import GUID

revision: str = "0011_profile_supabase_link"
down_revision: Union[str, None] = "0010_soft_delete_deleted_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("supabase_user_id", GUID(), nullable=True))
    op.create_unique_constraint("uq_profiles_supabase_user_id", "profiles", ["supabase_user_id"])
    op.create_index("ix_profiles_supabase_user_id", "profiles", ["supabase_user_id"])


def downgrade() -> None:
    op.drop_index("ix_profiles_supabase_user_id", table_name="profiles")
    op.drop_constraint("uq_profiles_supabase_user_id", "profiles", type_="unique")
    op.drop_column("profiles", "supabase_user_id")
```

- [ ] **Step 6: Verify head + run suite**

Run: `cd backend && python -m alembic heads && python -m pytest tests/test_profile_supabase_link.py -q`
Expected: head is `0011_profile_supabase_link`; test passes.

- [ ] **Step 7: Commit**

```bash
git add backend/app/domain/users.py backend/alembic/versions/0011_profile_supabase_link.py backend/tests/test_profile_supabase_link.py
git commit -m "feat(db): add profiles.supabase_user_id mapping + migration 0011"
```

---

## Task 4: Service-role credential resolver

**Files:**
- Create: `backend/app/services/supabase_auth_service.py`
- Test: `backend/tests/test_supabase_auth_service.py`

**Interfaces:**
- Consumes: `app.core.config.settings`, `IntegrationConfig`, `app.core.secrets.decrypt_secret`, `supabase_sync_service.SUPABASE_PROVIDER_ID`.
- Produces: `get_service_credentials(db: Session, workspace_id: uuid.UUID | None) -> tuple[str | None, str | None]` returning `(url, service_role_key)`. Per-workspace `IntegrationConfig` first, then env-level `settings.SUPABASE_URL` / `settings.SUPABASE_SERVICE_ROLE_KEY`, else `(None, None)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_supabase_auth_service.py
"""Supabase Auth provisioning service: credential resolution + admin create_user."""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

from app.services import supabase_auth_service


def test_get_service_credentials_env_fallback(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://envproj.supabase.co", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "env-service-role", raising=False)

    url, key = supabase_auth_service.get_service_credentials(db_session, workspace_id=None)
    assert url == "https://envproj.supabase.co"
    assert key == "env-service-role"


def test_get_service_credentials_none_when_unset(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "", raising=False)

    assert supabase_auth_service.get_service_credentials(db_session, workspace_id=None) == (None, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_supabase_auth_service.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.supabase_auth_service`.

- [ ] **Step 3: Implement the resolver**

```python
# backend/app/services/supabase_auth_service.py
"""Supabase Auth provisioning — create a GoTrue auth user for each AllHaven user.

Best-effort and never blocks the main flow: all failures are logged at debug and
never raised to callers. The service_role key and the user password are NEVER
logged or returned. Admin calls use the service_role key (not the anon key).
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.supabase_sync_service import SUPABASE_PROVIDER_ID

log = logging.getLogger(__name__)


def get_service_credentials(
    db: Session, workspace_id: Optional[uuid.UUID]
) -> tuple[Optional[str], Optional[str]]:
    """Return (url, service_role_key): per-workspace IntegrationConfig first, then env."""
    if workspace_id is not None:
        from app.domain.integrations import IntegrationConfig

        row = db.scalar(
            select(IntegrationConfig).where(
                IntegrationConfig.workspace_id == workspace_id,
                IntegrationConfig.provider_id == SUPABASE_PROVIDER_ID,
                IntegrationConfig.enabled == True,  # noqa: E712
            )
        )
        if row:
            url = (row.public_config or {}).get("url") or ""
            key = ""
            if row.encrypted_secrets:
                try:
                    from app.core.secrets import decrypt_secret

                    raw = row.encrypted_secrets.get("service_role_key")
                    if raw:
                        key = decrypt_secret(raw)
                except Exception:  # pragma: no cover - defensive
                    key = ""
            if url and key:
                return url, key

    url = settings.SUPABASE_URL or ""
    key = settings.SUPABASE_SERVICE_ROLE_KEY or ""
    return (url or None, key or None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_supabase_auth_service.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/supabase_auth_service.py backend/tests/test_supabase_auth_service.py
git commit -m "feat(auth): supabase_auth_service service-role credential resolver"
```

---

## Task 5: GoTrue admin `create_user`

**Files:**
- Modify: `backend/app/services/supabase_auth_service.py`
- Test: `backend/tests/test_supabase_auth_service.py`

**Interfaces:**
- Produces: `create_user(url: str, service_role_key: str, *, email: str, password: str, full_name: str | None) -> str | None` — POSTs `{url}/auth/v1/admin/users` with `apikey` + `Authorization: Bearer <service_role>`, body `{email, password, email_confirm: true, user_metadata: {full_name}}`, returns the Supabase user `id` from the response (or `None` on failure). Never raises.

- [ ] **Step 1: Write the failing test (append to the test file)**

```python
def test_create_user_posts_admin_request_with_service_role():
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.get_full_url()
        captured["headers"] = {k.lower(): v for k, v in dict(req.headers).items()}
        captured["body"] = json.loads(req.data.decode())
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.read = lambda: b'{"id": "11111111-1111-1111-1111-111111111111", "email": "x@example.com"}'
        return resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        sb_id = supabase_auth_service.create_user(
            "https://proj.supabase.co",
            "the-service-role-key",
            email="x@example.com",
            password="password123",
            full_name="Ex",
        )

    assert sb_id == "11111111-1111-1111-1111-111111111111"
    assert captured["url"] == "https://proj.supabase.co/auth/v1/admin/users"
    assert captured["headers"]["apikey"] == "the-service-role-key"
    assert captured["headers"]["authorization"] == "Bearer the-service-role-key"
    assert captured["body"]["email"] == "x@example.com"
    assert captured["body"]["email_confirm"] is True
    assert captured["body"]["user_metadata"]["full_name"] == "Ex"


def test_create_user_returns_none_on_http_error():
    def boom(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", side_effect=boom):
        assert (
            supabase_auth_service.create_user(
                "https://proj.supabase.co", "k", email="x@e.com", password="p", full_name=None
            )
            is None
        )
```

(Add `import urllib.error` to the test imports.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_supabase_auth_service.py -k create_user -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'create_user'`.

- [ ] **Step 3: Implement `create_user`**

Append to `supabase_auth_service.py`:

```python
def create_user(
    url: str,
    service_role_key: str,
    *,
    email: str,
    password: str,
    full_name: Optional[str],
) -> Optional[str]:
    """Create a Supabase Auth user via GoTrue admin. Returns the new user id, or None.

    Best-effort: never raises, never logs the key/password.
    """
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"full_name": full_name} if full_name else {},
    }
    req = urllib.request.Request(
        f"{url.rstrip('/')}/auth/v1/admin/users",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
        sb_id = body.get("id")
        return str(sb_id) if sb_id else None
    except urllib.error.HTTPError as exc:
        # 422 user_already_exists is non-fatal (idempotent re-provision).
        log.debug("Supabase create_user HTTP %s", exc.code)
        return None
    except Exception as exc:  # pragma: no cover - network defensive
        log.debug("Supabase create_user failed: %s", type(exc).__name__)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_supabase_auth_service.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/supabase_auth_service.py backend/tests/test_supabase_auth_service.py
git commit -m "feat(auth): GoTrue admin create_user (best-effort, service-role)"
```

---

## Task 6: Provision on signup (wire into `register_user`)

**Files:**
- Modify: `backend/app/services/auth_service.py` (`register_user`, `:33-72`)
- Test: `backend/tests/test_register_provisions_supabase.py`

**Interfaces:**
- Consumes: `supabase_auth_service.get_service_credentials`, `supabase_auth_service.create_user`.
- Behavior: after `db.flush()` (user.id known) and before `db.commit()`, if env-level service creds exist, call `create_user` and set `profile.supabase_user_id` from the returned id. A Supabase failure must NOT raise or roll back local registration.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_register_provisions_supabase.py
"""register_user provisions a Supabase Auth user when env creds are set; no-op otherwise."""
from __future__ import annotations

import uuid
from unittest.mock import patch

from app.services import auth_service


def test_register_provisions_and_stores_supabase_id(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://proj.supabase.co", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "svc", raising=False)
    sb_id = "22222222-2222-2222-2222-222222222222"

    with patch("app.services.supabase_auth_service.create_user", return_value=sb_id) as mock_create:
        user, workspace = auth_service.register_user(
            db_session, email="prov@example.com", password="password123", full_name="Prov"
        )

    mock_create.assert_called_once()
    from app.domain.users import Profile

    profile = db_session.get(Profile, user.id)
    assert str(profile.supabase_user_id) == sb_id


def test_register_no_supabase_when_unconfigured(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "", raising=False)

    with patch("app.services.supabase_auth_service.create_user") as mock_create:
        user, _ = auth_service.register_user(
            db_session, email="noprov@example.com", password="password123", full_name="No"
        )

    mock_create.assert_not_called()
    from app.domain.users import Profile

    assert db_session.get(Profile, user.id).supabase_user_id is None


def test_register_survives_supabase_failure(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://proj.supabase.co", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "svc", raising=False)

    with patch("app.services.supabase_auth_service.create_user", return_value=None):
        user, _ = auth_service.register_user(
            db_session, email="fail@example.com", password="password123", full_name="Fail"
        )

    assert user.id is not None  # local registration still committed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_register_provisions_supabase.py -v`
Expected: FAIL — `mock_create` not called (provisioning not wired yet).

- [ ] **Step 3: Wire provisioning into `register_user`**

In `backend/app/services/auth_service.py`, inside `register_user`, replace the block from the `membership` add through `db.commit()` so provisioning happens after flush and before commit:

```python
    membership = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    db.add(membership)

    write_audit(
        db,
        action="CREATE",
        entity_name="local_user",
        workspace_id=workspace.id,
        user_id=user.id,
        entity_id=user.id,
        after={"email": email},
    )

    # Best-effort: provision a matching Supabase Auth user (env-level creds only at
    # signup — no workspace IntegrationConfig exists yet). Never blocks/raises.
    from app.services import supabase_auth_service

    sb_url, sb_key = supabase_auth_service.get_service_credentials(db, workspace_id=None)
    if sb_url and sb_key:
        sb_id = supabase_auth_service.create_user(
            sb_url, sb_key, email=email, password=password, full_name=full_name
        )
        if sb_id:
            profile.supabase_user_id = sb_id

    db.commit()
    db.refresh(user)
    db.refresh(workspace)
    return user, workspace
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_register_provisions_supabase.py tests/test_auth.py -v`
Expected: PASS (new tests + existing register tests unaffected).

- [ ] **Step 5: Run the full suite (the `auth_client` fixture registers a user — confirm no network calls fire)**

Run: `cd backend && python -m pytest -q`
Expected: all pass. (SUPABASE_* are empty in `conftest.py`, so provisioning is skipped suite-wide.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/auth_service.py backend/tests/test_register_provisions_supabase.py
git commit -m "feat(auth): provision Supabase Auth user on signup (best-effort)"
```

---

## Task 7: "Connect to Supabase" endpoint (existing users)

**Files:**
- Modify: `backend/app/schemas/integrations.py` (add `SupabaseConnectRequest`)
- Modify: `backend/app/services/supabase_auth_service.py` (add `connect`)
- Modify: `backend/app/api/routers/settings.py` (add route)
- Test: `backend/tests/test_supabase_connect.py`

**Interfaces:**
- Consumes: `auth_service.authenticate`, `get_service_credentials`, `create_user`.
- Produces: `connect(db, principal, password) -> dict` and `POST /settings/supabase/connect`. Re-verifies the password; on success provisions + stores `supabase_user_id` and returns a small status dict. Wrong password → `InvalidCredentialsError` (mapped to HTTP 400/422, NOT 401, so the client session isn't cleared).

- [ ] **Step 1: Add the request schema**

In `backend/app/schemas/integrations.py`, beside `IntegrationUpdateRequest`:

```python
class SupabaseConnectRequest(BaseModel):
    password: str = Field(min_length=1)
```

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_supabase_connect.py
"""POST /settings/supabase/connect re-verifies the password then provisions Supabase Auth."""
from __future__ import annotations

from unittest.mock import patch

from tests.conftest import API


def test_connect_supabase_success(auth_client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://proj.supabase.co", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "svc", raising=False)

    with patch(
        "app.services.supabase_auth_service.create_user",
        return_value="33333333-3333-3333-3333-333333333333",
    ) as mock_create:
        resp = auth_client.post(f"{API}/settings/supabase/connect", json={"password": "password123"})

    assert resp.status_code == 200, resp.text
    mock_create.assert_called_once()


def test_connect_supabase_wrong_password(auth_client):
    resp = auth_client.post(f"{API}/settings/supabase/connect", json={"password": "WRONG"})
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 401  # must not log the user out
```

(The `auth_client` fixture registers `owner@example.com` with password `password123`.)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_supabase_connect.py -v`
Expected: FAIL — 404 (route missing).

- [ ] **Step 4: Implement the service `connect`**

Append to `supabase_auth_service.py` (import the project's error type used for bad input — check `app/core/exceptions.py` for the right class, e.g. `ValidationError`/`InvalidCredentialsError`; use the one that maps to HTTP 400/422, NOT the 401 path):

```python
def connect(db: Session, principal, password: str) -> dict:
    """Re-verify the user's password, then provision their Supabase Auth user."""
    from app.core.exceptions import ValidationError
    from app.services import auth_service

    user = auth_service.authenticate(db, email=principal.email, password=password)
    if not user:
        raise ValidationError("Incorrect password.", error_code="INVALID_PASSWORD")

    url, key = get_service_credentials(db, principal.workspace_id)
    if not url or not key:
        raise ValidationError(
            "Supabase service role key is not configured.", error_code="SUPABASE_NOT_CONFIGURED"
        )

    sb_id = create_user(
        url, key, email=principal.email, password=password, full_name=principal.full_name
    )
    if sb_id:
        from app.domain.users import Profile

        profile = db.get(Profile, principal.user_id)
        if profile is not None:
            profile.supabase_user_id = sb_id
            db.commit()
    return {"connected": bool(sb_id)}
```

> Verify `ValidationError(message, error_code=...)` exists in `app/core/exceptions.py` and maps to a 4xx that is NOT 401. If the project's class name/signature differs, use the matching one (the codebase already raises `ConflictError(message, error_code="EMAIL_TAKEN")` from this module family).

- [ ] **Step 5: Implement the route**

In `backend/app/api/routers/settings.py`, add (mirror the existing handler signature; import `SupabaseConnectRequest` and `supabase_auth_service`):

```python
@router.post("/supabase/connect")
def connect_supabase(
    payload: SupabaseConnectRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    result = supabase_auth_service.connect(db, principal, payload.password)
    return success_response(result, "Supabase Auth connected")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_supabase_connect.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/integrations.py backend/app/services/supabase_auth_service.py backend/app/api/routers/settings.py backend/tests/test_supabase_connect.py
git commit -m "feat(auth): POST /settings/supabase/connect for existing users"
```

---

## Task 8: Frontend "Connect to Supabase" control

**Files:**
- Modify: `frontend/lib/api.ts` (`settingsApi`, `:398-414`)
- Modify: `frontend/components/settings/IntegrationConfigModal.tsx`

**Interfaces:**
- Consumes: `request`, `json`, `ApiException` (already in `api.ts`).
- Produces: `settingsApi.connectSupabase(password: string)`; a password field + "Connect" button shown for the `supabase` integration.

> No JS unit-test runner exists in this repo, so these steps are verified by build + manual click-through, not unit tests.

- [ ] **Step 1: Add the API method**

In `frontend/lib/api.ts`, inside the `settingsApi` object:

```typescript
  connectSupabase: (password: string) =>
    request<{ connected: boolean }>("/settings/supabase/connect", {
      method: "POST",
      body: json({ password }),
    }),
```

- [ ] **Step 2: Add the UI control**

In `frontend/components/settings/IntegrationConfigModal.tsx`, when `integration.key === "supabase"`, render a password input + "Connect to Supabase" button that calls `settingsApi.connectSupabase`, following the existing `run()` busy/error pattern (clear the password after the call, surface `err instanceof ApiException ? err.message : "Action failed."`). Minimal addition:

```tsx
{integration.key === "supabase" ? (
  <div className="mt-4 border-t border-border pt-4">
    <label className="text-sm text-content-muted">Confirm your password to link Supabase Auth</label>
    <input
      type="password"
      value={connectPassword}
      onChange={(e) => setConnectPassword(e.target.value)}
      className="mt-1 w-full rounded-md border border-border bg-transparent px-3 py-2 text-sm"
    />
    <Button
      className="mt-2"
      disabled={busy === "connect" || !connectPassword}
      onClick={async () => {
        setBusy("connect");
        setError(null);
        try {
          await settingsApi.connectSupabase(connectPassword);
          setConnectPassword("");
        } catch (err) {
          setError(err instanceof ApiException ? err.message : "Action failed.");
        } finally {
          setBusy("");
        }
      }}
    >
      Connect to Supabase
    </Button>
  </div>
) : null}
```

Add `const [connectPassword, setConnectPassword] = useState("");` alongside the component's other `useState` hooks, and widen the `busy` state's type/union to include `"connect"` if it is a string-literal union.

- [ ] **Step 3: Verify the frontend builds**

Run: `cd frontend && npm run build` (or the project's lint/typecheck). Expected: compiles with no type errors. *(Node is required; if unavailable locally, rely on CI.)*

- [ ] **Step 4: Manual verification (document result in the PR)**

Log in as an existing user → Settings → Connected Tools → Supabase → enter password → "Connect to Supabase" → expect a success toast and no logout. Wrong password → inline error, still logged in.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/components/settings/IntegrationConfigModal.tsx
git commit -m "feat(settings): Connect to Supabase control (mobile auth provisioning)"
```

---

## Task 9: Postgres `updated_at` trigger migration

**Files:**
- Create: `backend/alembic/versions/0012_updated_at_trigger.py`

**Interfaces:**
- Produces: a `set_updated_at()` trigger function + `BEFORE UPDATE` triggers on every timestamped table, **on local Postgres and Supabase** (no-op on SQLite). Makes `updated_at` authoritative regardless of write path — required by Plan 2's LWW. The trigger **preserves an explicitly-supplied `updated_at`** (so the sync engine can apply a peer's timestamp): it only bumps `updated_at` when the writer left it unchanged.

- [ ] **Step 1: Write the migration**

```python
# backend/alembic/versions/0012_updated_at_trigger.py
"""DB-authoritative updated_at trigger (Postgres only)

Revision ID: 0012_updated_at_trigger
Revises: 0011_profile_supabase_link
Create Date: 2026-06-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_updated_at_trigger"
down_revision: Union[str, None] = "0011_profile_supabase_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables carrying TimestampMixin (created_at + updated_at).
_TS_TABLES = [
    "local_users", "profiles", "user_sessions", "workspaces", "workspace_members",
    "tasks", "task_checklist_items", "notes", "finance_categories", "transactions",
    "calendar_events", "drive_files", "automations", "weather_locations",
    "integration_configs", "ai_agent_configs", "chat_groups", "chat_sessions",
    "ai_multi_agent_runs", "ai_memories", "ai_conversation_summaries",
    "ai_knowledge_documents",
]

_FN = """
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  -- Preserve an explicitly-set updated_at (sync applying a peer row); otherwise bump.
  IF NEW.updated_at IS NOT DISTINCT FROM OLD.updated_at THEN
    NEW.updated_at = now();
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(sa.text(_FN))
    for table in _TS_TABLES:
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS trg_set_updated_at ON "{table}";'))
        op.execute(
            sa.text(
                f'CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON "{table}" '
                f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in _TS_TABLES:
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS trg_set_updated_at ON "{table}";'))
    op.execute(sa.text("DROP FUNCTION IF EXISTS set_updated_at();"))
```

- [ ] **Step 2: Verify the head + suite (SQLite no-op must not break tests)**

Run: `cd backend && python -m alembic heads && python -m pytest -q`
Expected: head is `0012_updated_at_trigger`; full suite passes (migration is a no-op on the SQLite test DB).

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/0012_updated_at_trigger.py
git commit -m "feat(db): migration 0012 DB-authoritative updated_at trigger (Postgres)"
```

---

## Task 10: Supabase-only RLS migration (env-guarded)

**Files:**
- Create: `backend/alembic/versions/0013_supabase_rls.py`
- Modify: `.env.example` (document `ALLHAVEN_DB_TARGET`)

**Interfaces:**
- Produces: revision `0013_supabase_rls`. When `ALLHAVEN_DB_TARGET=supabase`, it creates `app_user_id()` + `is_member()` helpers, enables RLS, and writes policies. When the env var is unset (local Postgres / CI / SQLite tests), `upgrade()` stamps the revision but runs **no DDL** — so a normal `alembic upgrade head` is safe everywhere.

- [ ] **Step 1: Write the migration**

```python
# backend/alembic/versions/0013_supabase_rls.py
"""Supabase-only RLS, helpers, and policies (guarded by ALLHAVEN_DB_TARGET=supabase)

Revision ID: 0013_supabase_rls
Revises: 0012_updated_at_trigger
Create Date: 2026-06-18
"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_supabase_rls"
down_revision: Union[str, None] = "0012_updated_at_trigger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WORKSPACE_TABLES = [
    "tasks", "task_checklist_items", "notes", "finance_categories", "transactions",
    "calendar_events", "drive_files", "automations", "weather_locations",
    "integration_configs", "ai_agent_configs", "chat_groups", "chat_sessions",
    "chat_messages", "ai_tool_proposals", "ai_tool_calls", "ai_multi_agent_runs",
    "ai_agent_responses", "ai_memories", "ai_memory_suggestions",
    "ai_conversation_summaries", "ai_knowledge_documents", "ai_knowledge_chunks",
]
# Locked down (RLS on, no policy = deny all): auth/secret tables never exposed to clients.
_DENY_TABLES = ["local_users", "user_sessions"]

_HELPERS = """
CREATE OR REPLACE FUNCTION app_user_id() RETURNS uuid AS $$
  SELECT id FROM public.profiles WHERE supabase_user_id = auth.uid();
$$ LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION is_member(ws uuid) RETURNS boolean AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = ws AND m.user_id = app_user_id()
  );
$$ LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public;
"""


def _enabled() -> bool:
    return os.getenv("ALLHAVEN_DB_TARGET", "").lower() == "supabase"


def upgrade() -> None:
    if not _enabled():
        return
    op.execute(sa.text(_HELPERS))

    for t in _WORKSPACE_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{t}" ENABLE ROW LEVEL SECURITY;'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS p_select ON "{t}";'))
        op.execute(sa.text(
            f'CREATE POLICY p_select ON "{t}" FOR SELECT TO authenticated '
            f"USING (is_member(workspace_id));"
        ))
        op.execute(sa.text(f'DROP POLICY IF EXISTS p_mod ON "{t}";'))
        op.execute(sa.text(
            f'CREATE POLICY p_mod ON "{t}" FOR ALL TO authenticated '
            f"USING (is_member(workspace_id)) WITH CHECK (is_member(workspace_id));"
        ))

    # User-scoped tables.
    op.execute(sa.text('ALTER TABLE "profiles" ENABLE ROW LEVEL SECURITY;'))
    op.execute(sa.text('DROP POLICY IF EXISTS p_self ON "profiles";'))
    op.execute(sa.text(
        'CREATE POLICY p_self ON "profiles" FOR ALL TO authenticated '
        "USING (id = app_user_id()) WITH CHECK (id = app_user_id());"
    ))
    op.execute(sa.text('ALTER TABLE "workspaces" ENABLE ROW LEVEL SECURITY;'))
    op.execute(sa.text('DROP POLICY IF EXISTS p_owner ON "workspaces";'))
    op.execute(sa.text(
        'CREATE POLICY p_owner ON "workspaces" FOR ALL TO authenticated '
        "USING (owner_id = app_user_id()) WITH CHECK (owner_id = app_user_id());"
    ))
    op.execute(sa.text('ALTER TABLE "workspace_members" ENABLE ROW LEVEL SECURITY;'))
    op.execute(sa.text('DROP POLICY IF EXISTS p_member ON "workspace_members";'))
    op.execute(sa.text(
        'CREATE POLICY p_member ON "workspace_members" FOR ALL TO authenticated '
        "USING (user_id = app_user_id()) WITH CHECK (user_id = app_user_id());"
    ))

    # audit_logs: workspace_id is nullable → only show member rows, hide NULL-scoped.
    op.execute(sa.text('ALTER TABLE "audit_logs" ENABLE ROW LEVEL SECURITY;'))
    op.execute(sa.text('DROP POLICY IF EXISTS p_audit ON "audit_logs";'))
    op.execute(sa.text(
        'CREATE POLICY p_audit ON "audit_logs" FOR SELECT TO authenticated '
        "USING (workspace_id IS NOT NULL AND is_member(workspace_id));"
    ))

    for t in _DENY_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{t}" ENABLE ROW LEVEL SECURITY;'))  # no policy = deny all


def downgrade() -> None:
    if not _enabled():
        return
    for t in _WORKSPACE_TABLES + ["profiles", "workspaces", "workspace_members", "audit_logs"] + _DENY_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{t}" DISABLE ROW LEVEL SECURITY;'))
    op.execute(sa.text("DROP FUNCTION IF EXISTS is_member(uuid);"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS app_user_id();"))
```

- [ ] **Step 2: Document the env var**

In `.env.example`, add near the Supabase section:

```
# Set to "supabase" ONLY when running `alembic upgrade head` against the Supabase
# database (enables RLS + policies). Leave empty for the local Postgres database.
ALLHAVEN_DB_TARGET=
```

- [ ] **Step 3: Verify local upgrade is a no-op (guard works) + suite passes**

Run: `cd backend && python -m alembic heads && python -m pytest -q`
Expected: head is `0013_supabase_rls`; full suite passes (RLS skipped because `ALLHAVEN_DB_TARGET` is unset).

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/0013_supabase_rls.py .env.example
git commit -m "feat(db): migration 0013 Supabase-only RLS + helpers (env-guarded)"
```

---

## Task 11: Supabase stand-up runbook + docs

**Files:**
- Create/Modify: `docs/DEPLOYMENT.md` (add a "Stand up the Supabase database" section)

**Interfaces:**
- Produces: documented operator steps. No code.

- [ ] **Step 1: Document the stand-up procedure**

Add to `docs/DEPLOYMENT.md`:

```markdown
### Stand up the Supabase database (v3.7)

1. Create a Supabase project; copy the Postgres connection string and the
   service_role key.
2. Build the full schema + RLS on Supabase (run from `backend/`, using the
   **direct** connection or **session** pooler — not the transaction pooler):

   ```bash
   DATABASE_URL="postgresql+psycopg://postgres:<pwd>@db.<ref>.supabase.co:5432/postgres" \
   ALLHAVEN_DB_TARGET=supabase \
   python -m alembic upgrade head
   ```

3. Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in the backend `.env` so
   new signups provision a Supabase Auth user automatically.
4. The local Postgres database is migrated normally (no `ALLHAVEN_DB_TARGET`),
   so RLS is skipped there.
```

- [ ] **Step 2: Commit**

```bash
git add docs/DEPLOYMENT.md
git commit -m "docs(3.7): Supabase database stand-up runbook"
```

---

## Self-Review

**Spec coverage (§A, §B):**
- §A schema stand-up → Task 11 runbook; portable migrations reused. ✓
- §A RLS (workspace + user-scoped + audit nullable + deny auth tables + non-recursive via `is_member`/`app_user_id`) → Task 10. ✓
- §A `updated_at` trigger (authoritative, preserves explicit) → Task 9. ✓
- §A key handling (service_role server-only) → Global Constraints + Task 4/5. ✓
- §B identity mapping (`supabase_user_id`, `app_user_id()`) → Task 3 + Task 10. ✓
- §B provisioning on signup (env creds) → Task 6; existing users ("Connect to Supabase") → Task 7/8. ✓
- §B mobile login via Supabase Auth → Plan 3 (out of scope here; provisioning is the prerequisite, delivered). ✓
- §10 data-model changes (`deleted_at`, `supabase_user_id`, RLS migration) → Tasks 1–3, 10. ✓ (`sync_state` is Plan 2.)

**Placeholder scan:** No TBD/TODO. Two "verify the exact error class / import line" notes (Task 3 GUID import, Task 7 `ValidationError`) are explicit verification instructions with the concrete fallback named, not placeholders.

**Type consistency:** `get_service_credentials(db, workspace_id)` → `(url, key)` used identically in Tasks 4/6/7. `create_user(url, key, *, email, password, full_name) -> str | None` consistent in Tasks 5/6/7. `connect(db, principal, password) -> dict` matches the route in Task 7. `supabase_user_id` column name consistent across Tasks 3/6/7/10. Migration chain is linear: `0009 → 0010 → 0011 → 0012 → 0013`.

**Out of scope (correctly deferred):** `sync_state` + push/pull/LWW worker (Plan 2); `apiSupabase.ts` + `DATA_MODE` + CRUD port + mobile Supabase login (Plan 3); AI/integrations/automations/Storage via Edge Functions (3.8/3.9).
