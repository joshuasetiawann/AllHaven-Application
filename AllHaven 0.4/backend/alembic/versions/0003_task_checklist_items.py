"""task checklist items

Revision ID: 0003_task_checklist_items
Revises: 0002_integration_ai_configs
Create Date: 2026-06-05

Adds task_checklist_items (max 5 per task, enforced in the service layer).
Existing tables/data untouched. Reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.domain.base import GUID

revision: str = "0003_task_checklist_items"
down_revision: Union[str, None] = "0002_integration_ai_configs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_checklist_items",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("task_id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("is_done", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_task_checklist_items"),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name="fk_task_checklist_items_task_id_tasks", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_task_checklist_items_task_id", "task_checklist_items", ["task_id"])
    op.create_index("ix_task_checklist_items_workspace_id", "task_checklist_items", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("task_checklist_items")
