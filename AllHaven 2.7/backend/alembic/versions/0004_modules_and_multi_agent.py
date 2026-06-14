"""multi-agent runs + module tables (calendar, drive, automations, weather)

Revision ID: 0004_modules_and_multi_agent
Revises: 0003_task_checklist_items
Create Date: 2026-06-05

Adds:
    * ai_multi_agent_runs / ai_agent_responses  (multi-agent AI chat)
    * calendar_events                           (local calendar)
    * drive_files                               (local Drive metadata)
    * automations                               (local automation drafts)
    * weather_locations                         (saved weather locations)

Existing tables/data are untouched. Reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.domain.base import GUID, StringArray

revision: str = "0004_modules_and_multi_agent"
down_revision: Union[str, None] = "0003_task_checklist_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_multi_agent_runs",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("session_id", GUID(), nullable=True),
        sa.Column("user_message_id", GUID(), nullable=True),
        sa.Column("provider_ids", StringArray(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'running'"), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_multi_agent_runs"),
    )
    op.create_index("ix_ai_multi_agent_runs_workspace_id", "ai_multi_agent_runs", ["workspace_id"])
    op.create_index("ix_ai_multi_agent_runs_session_id", "ai_multi_agent_runs", ["session_id"])

    op.create_table(
        "ai_agent_responses",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("run_id", GUID(), nullable=False),
        sa.Column("provider_id", sa.String(length=50), nullable=False),
        sa.Column("provider_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_agent_responses"),
    )
    op.create_index("ix_ai_agent_responses_workspace_id", "ai_agent_responses", ["workspace_id"])
    op.create_index("ix_ai_agent_responses_run_id", "ai_agent_responses", ["run_id"])

    op.create_table(
        "calendar_events",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("all_day", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_calendar_events"),
    )
    op.create_index("ix_calendar_events_workspace_id", "calendar_events", ["workspace_id"])

    op.create_table(
        "drive_files",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=127), server_default=sa.text("'application/octet-stream'"), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_drive_files"),
    )
    op.create_index("ix_drive_files_workspace_id", "drive_files", ["workspace_id"])

    op.create_table(
        "automations",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.String(length=60), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("action_type", sa.String(length=60), server_default=sa.text("'noop'"), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_automations"),
    )
    op.create_index("ix_automations_workspace_id", "automations", ["workspace_id"])

    op.create_table(
        "weather_locations",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_weather_locations"),
    )
    op.create_index("ix_weather_locations_workspace_id", "weather_locations", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("weather_locations")
    op.drop_table("automations")
    op.drop_table("drive_files")
    op.drop_table("calendar_events")
    op.drop_table("ai_agent_responses")
    op.drop_table("ai_multi_agent_runs")
