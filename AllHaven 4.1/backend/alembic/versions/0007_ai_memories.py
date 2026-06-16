"""ai_memories, ai_memory_suggestions, ai_conversation_summaries

Revision ID: 0007_ai_memories
Revises: 0006_user_sessions
Create Date: 2026-06-12

Adds:
    * ai_memories               (persistent user memories scoped to workspace)
    * ai_memory_suggestions     (pending approval for extracted memory candidates)
    * ai_conversation_summaries (cached per-session summaries)

Existing tables/data are untouched. Reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.domain.base import GUID

revision: str = "0007_ai_memories"
down_revision: Union[str, None] = "0006_user_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_memories",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("category", sa.String(length=50), server_default=sa.text("'Profile'"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=30), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("sensitivity", sa.String(length=10), server_default=sa.text("'LOW'"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default=sa.text("1.0"), nullable=False),
        sa.Column("relevance_score", sa.Float(), server_default=sa.text("0.5"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_session_id", GUID(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_memories"),
    )
    op.create_index("ix_ai_memories_workspace_id", "ai_memories", ["workspace_id"])

    op.create_table(
        "ai_memory_suggestions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("memory_id", GUID(), nullable=True),
        sa.Column("category", sa.String(length=50), server_default=sa.text("'Profile'"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_session_id", GUID(), nullable=True),
        sa.Column("source_snippet", sa.String(length=500), nullable=True),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.8"), nullable=False),
        sa.Column("sensitivity", sa.String(length=10), server_default=sa.text("'LOW'"), nullable=False),
        sa.Column("extraction_method", sa.String(length=20), server_default=sa.text("'rule_based'"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_memory_suggestions"),
    )
    op.create_index("ix_ai_memory_suggestions_workspace_id", "ai_memory_suggestions", ["workspace_id"])

    op.create_table(
        "ai_conversation_summaries",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("session_id", GUID(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("message_count_at_summary", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_conversation_summaries"),
        sa.UniqueConstraint("session_id", name="uq_ai_conversation_summaries_session_id"),
    )
    op.create_index("ix_ai_conversation_summaries_workspace_id", "ai_conversation_summaries", ["workspace_id"])
    op.create_index("ix_ai_conversation_summaries_session_id", "ai_conversation_summaries", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_conversation_summaries_session_id", table_name="ai_conversation_summaries")
    op.drop_index("ix_ai_conversation_summaries_workspace_id", table_name="ai_conversation_summaries")
    op.drop_table("ai_conversation_summaries")
    op.drop_index("ix_ai_memory_suggestions_workspace_id", table_name="ai_memory_suggestions")
    op.drop_table("ai_memory_suggestions")
    op.drop_index("ix_ai_memories_workspace_id", table_name="ai_memories")
    op.drop_table("ai_memories")
