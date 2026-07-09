import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.domain.sync_state import SyncState
from app.domain.tasks import Task
from app.core.database import SessionLocal
from app.services import sync_registry
from app.services import supabase_sync_service


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


# ---------------------------------------------------------------------------
# Task 3: sync_registry
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task 4: _deserialize
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task 5: push_table
# ---------------------------------------------------------------------------

from app.services import sync_engine  # noqa: E402


def _ws_with_task(db):
    ws = uuid.uuid4()
    user = uuid.uuid4()
    t = Task(workspace_id=ws, created_by=user, title="t1", status="TODO")
    db.add(t)
    db.commit()
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


# ---------------------------------------------------------------------------
# Task 6: pull_table — LWW merge + echo suppression
# ---------------------------------------------------------------------------

def test_pull_applies_remote_newer_and_suppresses_echo():
    db = SessionLocal()
    try:
        ws = uuid.uuid4()
        pk = uuid.uuid4()
        user = uuid.uuid4()
        local = Task(id=pk, workspace_id=ws, created_by=user, title="old", status="TODO",
                     updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        db.add(local)
        db.commit()
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
        ws = uuid.uuid4()
        pk = uuid.uuid4()
        user = uuid.uuid4()
        db.add(Task(id=pk, workspace_id=ws, created_by=user, title="local-newer", status="TODO",
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


def test_pull_keeps_local_when_remote_has_non_utc_offset_but_is_older():
    """Regression: remote row with +07:00 offset that is OLDER in UTC must not overwrite local.

    Local:  2026-02-01T05:00:00+00:00  (05:00 UTC)   — newer
    Remote: 2026-02-01T09:00:00+07:00  (02:00 UTC)   — older

    Before the fix, `.replace(tzinfo=None)` compared wall-clock numbers
    (09:00 > 05:00) and silently overwrote the newer local row.
    After the fix, `_to_utc_naive` converts to UTC first (02:00 < 05:00)
    and correctly keeps the local row.
    """
    db = SessionLocal()
    try:
        ws = uuid.uuid4()
        pk = uuid.uuid4()
        user = uuid.uuid4()
        # Local row: 05:00 UTC — the newer row
        local = Task(
            id=pk,
            workspace_id=ws,
            created_by=user,
            title="local-newer",
            status="TODO",
            updated_at=datetime(2026, 2, 1, 5, 0, 0, tzinfo=timezone.utc),
        )
        db.add(local)
        db.commit()

        spec = sync_registry.spec_for("tasks")
        # Remote row: 09:00+07:00 == 02:00 UTC — older instant, different title
        remote_row = {
            "id": str(pk),
            "workspace_id": str(ws),
            "title": "remote-older-with-tz-offset",
            "status": "TODO",
            "is_deleted": False,
            "created_at": "2026-02-01T09:00:00+07:00",
            "updated_at": "2026-02-01T09:00:00+07:00",
        }

        sync_engine.pull_table(
            db, "https://x", "svc", ws, [], spec,
            fetch=lambda *a: [remote_row],
        )

        db.refresh(local)
        assert local.title == "local-newer", (
            f"LWW violation: local row (05:00 UTC) was overwritten by remote row "
            f"(09:00+07:00 = 02:00 UTC), title is now {local.title!r}"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task 7: sync_two_way orchestrator
# ---------------------------------------------------------------------------

from unittest.mock import patch, MagicMock  # noqa: E402
from app.core.principal import Principal  # noqa: E402


def test_sync_two_way_skips_when_no_credentials(db_session):
    """sync_two_way returns 'skipped' and never raises when credentials are absent."""
    p = Principal(user_id=uuid.uuid4(), workspace_id=uuid.uuid4(), email="x@y.z")
    with patch("app.services.supabase_auth_service.get_service_credentials", return_value=(None, None)):
        out = sync_engine.sync_two_way(db_session, p)
    assert out["status"] == "skipped"


def test_sync_two_way_pulls_then_pushes(db_session, auth_client):
    """sync_two_way issues GET (pull) and POST (push) for each table when credentials exist."""
    from tests.test_supabase_sync import _make_principal
    p = _make_principal(auth_client)
    # one local task to push
    db_session.add(Task(workspace_id=p.workspace_id, created_by=p.user_id, title="local", status="TODO"))
    db_session.commit()
    captured = {"get": 0, "post": 0}

    def fake_urlopen(req, timeout=None):
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


# ---------------------------------------------------------------------------
# Task 8: per-write trigger rewired to two-way engine
# ---------------------------------------------------------------------------

import threading  # noqa: E402


def test_sync_after_write_invokes_two_way_engine(db_session):
    """sync_after_write spawns a daemon thread targeting the two-way engine worker."""
    p = Principal(user_id=uuid.uuid4(), workspace_id=uuid.uuid4(), email="x@y.z")
    calls = {}

    def capture_start(self):
        calls["target"] = getattr(self, "_target", None)
        # don't actually run the thread body

    from app.services import local_first_sync
    with patch.object(threading.Thread, "start", capture_start):
        local_first_sync.sync_after_write(db_session, p)
    # the spawned worker targets the two-way engine
    assert calls.get("target") is not None
