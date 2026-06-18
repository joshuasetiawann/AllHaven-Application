import uuid
from datetime import datetime, timezone
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
