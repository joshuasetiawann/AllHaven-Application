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
