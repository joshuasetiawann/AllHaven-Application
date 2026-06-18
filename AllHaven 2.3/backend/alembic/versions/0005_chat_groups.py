"""chat groups + conversation group_id

Revision ID: 0005_chat_groups
Revises: 0004_modules_and_multi_agent
Create Date: 2026-06-09

Adds chat_groups (projects) and a nullable chat_sessions.group_id so conversations
can be organized into groups. Existing data untouched. Reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.domain.base import GUID

revision: str = "0005_chat_groups"
down_revision: Union[str, None] = "0004_modules_and_multi_agent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_groups",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_chat_groups"),
    )
    op.create_index("ix_chat_groups_workspace_id", "chat_groups", ["workspace_id"])

    op.add_column("chat_sessions", sa.Column("group_id", GUID(), nullable=True))
    op.create_index("ix_chat_sessions_group_id", "chat_sessions", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_group_id", table_name="chat_sessions")
    op.drop_column("chat_sessions", "group_id")
    op.drop_index("ix_chat_groups_workspace_id", table_name="chat_groups")
    op.drop_table("chat_groups")
