# backend/alembic/versions/0013_supabase_rls.py
"""Supabase-only RLS, helpers, and policies (guarded by ALLHAVEN_DB_TARGET=supabase)

Revision ID: 0013_supabase_rls
Revises: 0012_updated_at_trigger
Create Date: 2026-06-18
"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_supabase_rls"
down_revision: Union[str, None] = "0012_updated_at_trigger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WORKSPACE_TABLES = [
    "tasks", "task_checklist_items", "notes", "finance_categories", "transactions",
    "calendar_events", "drive_files", "automations", "weather_locations",
    "integration_configs", "ai_agent_configs", "chat_groups", "chat_sessions",
    "chat_messages", "ai_tool_proposals", "ai_tool_calls", "ai_multi_agent_runs",
    "ai_agent_responses", "ai_memories", "ai_memory_suggestions",
    "ai_conversation_summaries", "ai_knowledge_documents", "ai_knowledge_chunks",
]
# Locked down (RLS on, no policy = deny all): auth/secret tables never exposed to clients.
_DENY_TABLES = ["local_users", "user_sessions"]

_HELPERS = """
CREATE OR REPLACE FUNCTION app_user_id() RETURNS uuid AS $$
  SELECT id FROM public.profiles WHERE supabase_user_id = auth.uid();
$$ LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION is_member(ws uuid) RETURNS boolean AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = ws AND m.user_id = app_user_id()
  );
$$ LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public;
"""


def _enabled() -> bool:
    return os.getenv("ALLHAVEN_DB_TARGET", "").lower() == "supabase"


def upgrade() -> None:
    if not _enabled():
        return
    op.execute(sa.text(_HELPERS))

    for t in _WORKSPACE_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{t}" ENABLE ROW LEVEL SECURITY;'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS p_select ON "{t}";'))
        op.execute(sa.text(
            f'CREATE POLICY p_select ON "{t}" FOR SELECT TO authenticated '
            f"USING (is_member(workspace_id));"
        ))
        op.execute(sa.text(f'DROP POLICY IF EXISTS p_mod ON "{t}";'))
        op.execute(sa.text(
            f'CREATE POLICY p_mod ON "{t}" FOR ALL TO authenticated '
            f"USING (is_member(workspace_id)) WITH CHECK (is_member(workspace_id));"
        ))

    # User-scoped tables.
    op.execute(sa.text('ALTER TABLE "profiles" ENABLE ROW LEVEL SECURITY;'))
    op.execute(sa.text('DROP POLICY IF EXISTS p_self ON "profiles";'))
    op.execute(sa.text(
        'CREATE POLICY p_self ON "profiles" FOR ALL TO authenticated '
        "USING (id = app_user_id()) WITH CHECK (id = app_user_id());"
    ))
    op.execute(sa.text('ALTER TABLE "workspaces" ENABLE ROW LEVEL SECURITY;'))
    op.execute(sa.text('DROP POLICY IF EXISTS p_owner ON "workspaces";'))
    op.execute(sa.text(
        'CREATE POLICY p_owner ON "workspaces" FOR ALL TO authenticated '
        "USING (owner_id = app_user_id()) WITH CHECK (owner_id = app_user_id());"
    ))
    op.execute(sa.text('ALTER TABLE "workspace_members" ENABLE ROW LEVEL SECURITY;'))
    op.execute(sa.text('DROP POLICY IF EXISTS p_member ON "workspace_members";'))
    op.execute(sa.text(
        'CREATE POLICY p_member ON "workspace_members" FOR ALL TO authenticated '
        "USING (user_id = app_user_id()) WITH CHECK (user_id = app_user_id());"
    ))

    # audit_logs: workspace_id is nullable → only show member rows, hide NULL-scoped.
    op.execute(sa.text('ALTER TABLE "audit_logs" ENABLE ROW LEVEL SECURITY;'))
    op.execute(sa.text('DROP POLICY IF EXISTS p_audit ON "audit_logs";'))
    op.execute(sa.text(
        'CREATE POLICY p_audit ON "audit_logs" FOR SELECT TO authenticated '
        "USING (workspace_id IS NOT NULL AND is_member(workspace_id));"
    ))

    for t in _DENY_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{t}" ENABLE ROW LEVEL SECURITY;'))  # no policy = deny all


def downgrade() -> None:
    if not _enabled():
        return
    for t in _WORKSPACE_TABLES + ["profiles", "workspaces", "workspace_members", "audit_logs"] + _DENY_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{t}" DISABLE ROW LEVEL SECURITY;'))
    op.execute(sa.text("DROP FUNCTION IF EXISTS is_member(uuid);"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS app_user_id();"))
