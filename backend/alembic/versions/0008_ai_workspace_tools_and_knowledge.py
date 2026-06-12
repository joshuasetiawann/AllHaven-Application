"""ai tool calls, section keys, and AI Knowledge

Revision ID: 0008_ai_workspace_tools
Revises: 0007_ai_memories
Create Date: 2026-06-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.domain.base import GUID

revision: str = "0008_ai_workspace_tools"
down_revision: Union[str, None] = "0007_ai_memories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_col(nullable: bool = True):
    return sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=nullable)


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("section_key", sa.String(length=50), server_default="general", nullable=False))
    op.add_column("chat_messages", sa.Column("section_key", sa.String(length=50), server_default="general", nullable=False))
    op.create_index("ix_chat_messages_section_key", "chat_messages", ["section_key"])

    op.create_table(
        "ai_tool_calls",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("session_id", GUID(), nullable=True),
        sa.Column("message_id", GUID(), nullable=True),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=True),
        sa.Column("access", sa.String(length=20), nullable=True),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_preview", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("proposal_id", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_tool_calls"),
    )
    op.create_index("ix_ai_tool_calls_workspace_id", "ai_tool_calls", ["workspace_id"])
    op.create_index("ix_ai_tool_calls_user_id", "ai_tool_calls", ["user_id"])
    op.create_index("ix_ai_tool_calls_session_id", "ai_tool_calls", ["session_id"])
    op.create_index("ix_ai_tool_calls_tool_name", "ai_tool_calls", ["tool_name"])
    op.create_index("ix_ai_tool_calls_status", "ai_tool_calls", ["status"])
    op.create_index("ix_ai_tool_calls_proposal_id", "ai_tool_calls", ["proposal_id"])

    op.create_table(
        "ai_knowledge_documents",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=127), server_default="application/octet-stream", nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="uploaded", nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("source_drive_file_id", GUID(), nullable=True),
        _json_col(),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_knowledge_documents"),
    )
    op.create_index("ix_ai_knowledge_documents_workspace_id", "ai_knowledge_documents", ["workspace_id"])
    op.create_index("ix_ai_knowledge_documents_created_by", "ai_knowledge_documents", ["created_by"])
    op.create_index("ix_ai_knowledge_documents_status", "ai_knowledge_documents", ["status"])

    op.create_table(
        "ai_knowledge_chunks",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("document_id", GUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        _json_col(),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_knowledge_chunks"),
    )
    op.create_index("ix_ai_knowledge_chunks_workspace_id", "ai_knowledge_chunks", ["workspace_id"])
    op.create_index("ix_ai_knowledge_chunks_document_id", "ai_knowledge_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_knowledge_chunks_document_id", table_name="ai_knowledge_chunks")
    op.drop_index("ix_ai_knowledge_chunks_workspace_id", table_name="ai_knowledge_chunks")
    op.drop_table("ai_knowledge_chunks")
    op.drop_index("ix_ai_knowledge_documents_status", table_name="ai_knowledge_documents")
    op.drop_index("ix_ai_knowledge_documents_created_by", table_name="ai_knowledge_documents")
    op.drop_index("ix_ai_knowledge_documents_workspace_id", table_name="ai_knowledge_documents")
    op.drop_table("ai_knowledge_documents")
    op.drop_index("ix_ai_tool_calls_proposal_id", table_name="ai_tool_calls")
    op.drop_index("ix_ai_tool_calls_status", table_name="ai_tool_calls")
    op.drop_index("ix_ai_tool_calls_tool_name", table_name="ai_tool_calls")
    op.drop_index("ix_ai_tool_calls_session_id", table_name="ai_tool_calls")
    op.drop_index("ix_ai_tool_calls_user_id", table_name="ai_tool_calls")
    op.drop_index("ix_ai_tool_calls_workspace_id", table_name="ai_tool_calls")
    op.drop_table("ai_tool_calls")
    op.drop_index("ix_chat_messages_section_key", table_name="chat_messages")
    op.drop_column("chat_messages", "section_key")
    op.drop_column("chat_sessions", "section_key")
