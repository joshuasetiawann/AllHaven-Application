# backend/alembic/versions/0012_updated_at_trigger.py
"""DB-authoritative updated_at trigger (Postgres only)

Revision ID: 0012_updated_at_trigger
Revises: 0011_profile_supabase_link
Create Date: 2026-06-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_updated_at_trigger"
down_revision: Union[str, None] = "0011_profile_supabase_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables carrying TimestampMixin (created_at + updated_at).
_TS_TABLES = [
    "local_users", "profiles", "user_sessions", "workspaces", "workspace_members",
    "tasks", "task_checklist_items", "notes", "finance_categories", "transactions",
    "calendar_events", "drive_files", "automations", "weather_locations",
    "integration_configs", "ai_agent_configs", "chat_groups", "chat_sessions",
    "ai_multi_agent_runs", "ai_memories", "ai_conversation_summaries",
    "ai_knowledge_documents",
]

_FN = """
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  -- Preserve an explicitly-set updated_at (sync applying a peer row); otherwise bump.
  IF NEW.updated_at IS NOT DISTINCT FROM OLD.updated_at THEN
    NEW.updated_at = now();
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(sa.text(_FN))
    for table in _TS_TABLES:
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS trg_set_updated_at ON "{table}";'))
        op.execute(
            sa.text(
                f'CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON "{table}" '
                f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in _TS_TABLES:
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS trg_set_updated_at ON "{table}";'))
    op.execute(sa.text("DROP FUNCTION IF EXISTS set_updated_at();"))
