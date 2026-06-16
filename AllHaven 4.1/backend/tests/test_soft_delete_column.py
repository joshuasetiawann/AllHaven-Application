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
    "ai_memories",
]


def test_soft_delete_tables_have_deleted_at():
    inspector = inspect(engine)
    for table in SOFT_DELETE_TABLES:
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        assert "deleted_at" in cols, f"{table} missing deleted_at"
        assert cols["deleted_at"]["nullable"] is True, f"{table}.deleted_at must be nullable"
