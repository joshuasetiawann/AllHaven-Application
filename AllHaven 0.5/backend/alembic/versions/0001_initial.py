"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-05

Creates the full CoreOS MVP schema: identity, workspaces, tasks, notes, finance,
AI chat/proposals, and audit logs. Uses the portable column types defined in
app.domain.base so the same definitions map to PostgreSQL native types.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.domain.base import GUID, JSONType, StringArray

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _updated_at() -> sa.Column:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    # --- local_users ---
    op.create_table(
        "local_users",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="pk_local_users"),
    )
    op.create_index("ix_local_users_email", "local_users", ["email"], unique=True)

    # --- profiles ---
    op.create_table(
        "profiles",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="pk_profiles"),
    )
    op.create_index("ix_profiles_email", "profiles", ["email"], unique=True)

    # --- workspaces ---
    op.create_table(
        "workspaces",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_id", GUID(), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
    )
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])

    # --- workspace_members ---
    op.create_table(
        "workspace_members",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_members"),
    )
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"])
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    # --- tasks ---
    op.create_table(
        "tasks",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=30), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="pk_tasks"),
    )
    op.create_index("ix_tasks_workspace_id", "tasks", ["workspace_id"])
    op.create_index("ix_tasks_is_deleted", "tasks", ["is_deleted"])

    # --- notes ---
    op.create_table(
        "notes",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tags", StringArray(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="pk_notes"),
    )
    op.create_index("ix_notes_workspace_id", "notes", ["workspace_id"])
    op.create_index("ix_notes_is_deleted", "notes", ["is_deleted"])

    # --- finance_categories ---
    op.create_table(
        "finance_categories",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="pk_finance_categories"),
    )
    op.create_index("ix_finance_categories_workspace_id", "finance_categories", ["workspace_id"])
    op.create_index("ix_finance_categories_is_deleted", "finance_categories", ["is_deleted"])

    # --- transactions ---
    op.create_table(
        "transactions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=True),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("category_id", GUID(), nullable=True),
        sa.Column("category_name_snapshot", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="pk_transactions"),
    )
    op.create_index("ix_transactions_workspace_id", "transactions", ["workspace_id"])
    op.create_index("ix_transactions_category_id", "transactions", ["category_id"])
    op.create_index("ix_transactions_transaction_date", "transactions", ["transaction_date"])
    op.create_index("ix_transactions_is_deleted", "transactions", ["is_deleted"])

    # --- chat_sessions ---
    op.create_table(
        "chat_sessions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="pk_chat_sessions"),
    )
    op.create_index("ix_chat_sessions_workspace_id", "chat_sessions", ["workspace_id"])

    # --- chat_messages ---
    op.create_table(
        "chat_messages",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("session_id", GUID(), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", JSONType, nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
    )
    op.create_index("ix_chat_messages_workspace_id", "chat_messages", ["workspace_id"])
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    # --- ai_tool_proposals ---
    op.create_table(
        "ai_tool_proposals",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("tool_payload", JSONType, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column(
            "requires_confirmation", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_ai_tool_proposals"),
    )
    op.create_index("ix_ai_tool_proposals_workspace_id", "ai_tool_proposals", ["workspace_id"])

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=True),
        sa.Column("user_id", GUID(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("entity_name", sa.String(length=100), nullable=False),
        sa.Column("entity_id", GUID(), nullable=True),
        sa.Column("before_data", JSONType, nullable=True),
        sa.Column("after_data", JSONType, nullable=True),
        sa.Column("metadata", JSONType, nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("ai_tool_proposals")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("transactions")
    op.drop_table("finance_categories")
    op.drop_table("notes")
    op.drop_table("tasks")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
    op.drop_table("profiles")
    op.drop_table("local_users")
