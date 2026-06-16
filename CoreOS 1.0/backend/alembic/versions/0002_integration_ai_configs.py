"""integration and ai agent configs

Revision ID: 0002_integration_ai_configs
Revises: 0001_initial
Create Date: 2026-06-05

Adds integration_configs and ai_agent_configs for web-configurable, workspace-
scoped integration credentials and AI provider preferences. Existing tables and
data are untouched. Reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.domain.base import GUID, JSONType

revision: str = "0002_integration_ai_configs"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "integration_configs",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("provider_id", sa.String(length=50), nullable=False),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("status", sa.String(length=30), server_default=sa.text("'not_configured'"), nullable=False),
        sa.Column("public_config", JSONType, nullable=False),
        sa.Column("encrypted_secrets", JSONType, nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="pk_integration_configs"),
        sa.UniqueConstraint("workspace_id", "provider_id", name="uq_integration_workspace_provider"),
    )
    op.create_index("ix_integration_configs_workspace_id", "integration_configs", ["workspace_id"])

    op.create_table(
        "ai_agent_configs",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("provider_id", sa.String(length=50), nullable=False),
        sa.Column("provider_type", sa.String(length=50), server_default=sa.text("'ai_provider'"), nullable=False),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(length=30), server_default=sa.text("'not_configured'"), nullable=False),
        sa.Column("default_model", sa.String(length=120), nullable=True),
        sa.Column("privacy_mode", sa.String(length=30), server_default=sa.text("'local_private'"), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("temperature", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("public_config", JSONType, nullable=False),
        sa.Column("encrypted_secrets", JSONType, nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="pk_ai_agent_configs"),
        sa.UniqueConstraint("workspace_id", "provider_id", name="uq_ai_agent_workspace_provider"),
    )
    op.create_index("ix_ai_agent_configs_workspace_id", "ai_agent_configs", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("ai_agent_configs")
    op.drop_table("integration_configs")
