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
