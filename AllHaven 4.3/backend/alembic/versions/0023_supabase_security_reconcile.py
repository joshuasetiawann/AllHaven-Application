"""Reconcile Supabase RLS and provisioning on already-migrated databases.

Revision ID: 0023_supabase_security
Revises: 0022_referential_integrity
Create Date: 2026-08-13

Earlier Supabase migrations were environment-guarded no-ops. Editing those
historical files cannot repair a database whose Alembic version has already
advanced past them, so this new head idempotently recreates the complete policy
set. Detection is based on the actual migration connection (``auth.users``),
not merely on how configuration happened to enter the process environment.
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_supabase_security"
down_revision: Union[str, None] = "0022_referential_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_WORKSPACE_TABLES = [
    "tasks", "task_checklist_items", "notes", "finance_categories", "transactions",
    "calendar_events", "drive_files", "automations", "weather_locations",
    "chat_groups", "chat_sessions",
    "chat_messages", "ai_tool_proposals", "ai_tool_calls", "ai_multi_agent_runs",
    "ai_agent_responses", "ai_memories", "ai_memory_suggestions",
    "ai_conversation_summaries", "ai_knowledge_documents", "ai_knowledge_chunks",
    "sync_state",
]
_DENY_TABLES = [
    "local_users",
    "user_sessions",
    # Provider configuration and ciphertext are backend-only. Mobile sync does
    # not need these rows, and authenticated PostgREST clients must not select
    # them even when they own the workspace.
    "integration_configs",
    "ai_agent_configs",
]


_HELPERS = """
CREATE OR REPLACE FUNCTION public.app_user_id() RETURNS uuid AS $$
  SELECT id FROM public.profiles WHERE supabase_user_id = auth.uid();
$$ LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION public.is_member(ws uuid) RETURNS boolean AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = ws AND m.user_id = public.app_user_id()
  );
$$ LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public;

REVOKE ALL ON FUNCTION public.app_user_id() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.is_member(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.app_user_id() TO authenticated;
GRANT EXECUTE ON FUNCTION public.is_member(uuid) TO authenticated;
"""


_PROVISION_FN = """
DROP FUNCTION IF EXISTS public.provision_me(text);

CREATE FUNCTION public.provision_me(p_full_name text DEFAULT NULL)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_uid uuid := auth.uid();
  v_email text;
  v_name text;
  v_profile_id uuid;
  v_ws_id uuid;
  v_created boolean := false;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'not authenticated' USING errcode = '28000';
  END IF;

  SELECT email, raw_user_meta_data->>'full_name'
    INTO v_email, v_name FROM auth.users WHERE id = v_uid;
  IF v_email IS NULL THEN
    RAISE EXCEPTION 'authenticated user has no email' USING errcode = '22023';
  END IF;
  v_name := COALESCE(NULLIF(p_full_name, ''), NULLIF(v_name, ''));

  SELECT id INTO v_profile_id FROM public.profiles WHERE supabase_user_id = v_uid;
  IF v_profile_id IS NULL THEN
    -- An authenticated caller controls their own Auth account, but projects may
    -- allow signup without proving control of the supplied email address.  Never
    -- let this SECURITY DEFINER function claim a desktop-created profile merely
    -- because the strings match; trusted backend provisioning links those rows.
    IF EXISTS (
      SELECT 1 FROM public.profiles WHERE lower(email) = lower(v_email)
    ) THEN
      RAISE EXCEPTION 'existing profile requires trusted backend linkage'
        USING errcode = '42501';
    END IF;

    v_profile_id := gen_random_uuid();
    INSERT INTO public.profiles
      (id, email, full_name, supabase_user_id, created_at, updated_at)
    VALUES (v_profile_id, v_email, v_name, v_uid, now(), now());
    v_created := true;
  END IF;

  SELECT id INTO v_ws_id FROM public.workspaces
   WHERE owner_id = v_profile_id ORDER BY created_at ASC LIMIT 1;
  IF v_ws_id IS NULL THEN
    v_ws_id := gen_random_uuid();
    INSERT INTO public.workspaces (id, name, owner_id, created_at, updated_at)
    VALUES (
      v_ws_id,
      COALESCE(v_name || '''s Workspace', 'My Workspace'),
      v_profile_id,
      now(),
      now()
    );
  END IF;

  INSERT INTO public.workspace_members
    (id, workspace_id, user_id, role, created_at, updated_at)
  SELECT gen_random_uuid(), v_ws_id, v_profile_id, 'owner', now(), now()
  WHERE NOT EXISTS (
    SELECT 1 FROM public.workspace_members
    WHERE workspace_id = v_ws_id AND user_id = v_profile_id
  );

  RETURN jsonb_build_object(
    'status', 'success',
    'created', v_created,
    'profile_id', v_profile_id,
    'workspace_id', v_ws_id
  );
END;
$$;

REVOKE ALL ON FUNCTION public.provision_me(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.provision_me(text) TO authenticated;
"""


def _is_supabase_target() -> bool:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return False

    explicit = os.getenv("ALLHAVEN_DB_TARGET", "").strip().lower()
    auth_users_exists = bool(bind.execute(sa.text(
        "SELECT to_regclass('auth.users') IS NOT NULL"
    )).scalar_one())
    if explicit == "supabase" and not auth_users_exists:
        raise RuntimeError(
            "ALLHAVEN_DB_TARGET=supabase, but the migration connection has no "
            "auth.users table. Check that Alembic is connected to the Supabase "
            "project database."
        )
    return auth_users_exists


def _drop_all_policies(table: str) -> None:
    """Remove the complete prior policy set before installing the final one.

    PostgreSQL policies are permissive by default and are ORed together.  Merely
    replacing policies with our expected names would therefore leave an old or
    operator-created ``USING (true)`` policy able to bypass the tenant boundary.
    All callers pass table names from fixed module-level allowlists.
    """
    op.execute(sa.text(f"""
        DO $policy_cleanup$
        DECLARE policy_row record;
        BEGIN
          FOR policy_row IN
            SELECT policyname FROM pg_policies
            WHERE schemaname = 'public' AND tablename = '{table}'
          LOOP
            EXECUTE format(
              'DROP POLICY IF EXISTS %I ON public.%I',
              policy_row.policyname,
              '{table}'
            );
          END LOOP;
        END
        $policy_cleanup$;
    """))


def upgrade() -> None:
    if not _is_supabase_target():
        return

    op.execute(sa.text(_HELPERS))
    for table in _WORKSPACE_TABLES:
        op.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY;'))
        _drop_all_policies(table)
        op.execute(sa.text(
            f'CREATE POLICY p_select ON public."{table}" FOR SELECT TO authenticated '
            "USING (public.is_member(workspace_id));"
        ))
        op.execute(sa.text(
            f'CREATE POLICY p_mod ON public."{table}" FOR ALL TO authenticated '
            "USING (public.is_member(workspace_id)) "
            "WITH CHECK (public.is_member(workspace_id));"
        ))

    op.execute(sa.text('ALTER TABLE public."profiles" ENABLE ROW LEVEL SECURITY;'))
    _drop_all_policies("profiles")
    op.execute(sa.text(
        'CREATE POLICY p_self ON public."profiles" FOR ALL TO authenticated '
        "USING (id = public.app_user_id()) WITH CHECK (id = public.app_user_id());"
    ))

    op.execute(sa.text('ALTER TABLE public."workspaces" ENABLE ROW LEVEL SECURITY;'))
    _drop_all_policies("workspaces")
    op.execute(sa.text(
        'CREATE POLICY p_owner ON public."workspaces" FOR ALL TO authenticated '
        "USING (owner_id = public.app_user_id()) WITH CHECK (owner_id = public.app_user_id());"
    ))

    op.execute(sa.text(
        'ALTER TABLE public."workspace_members" ENABLE ROW LEVEL SECURITY;'
    ))
    _drop_all_policies("workspace_members")
    op.execute(sa.text(
        'CREATE POLICY p_member ON public."workspace_members" FOR SELECT TO authenticated '
        "USING (user_id = public.app_user_id());"
    ))

    op.execute(sa.text('ALTER TABLE public."audit_logs" ENABLE ROW LEVEL SECURITY;'))
    _drop_all_policies("audit_logs")
    op.execute(sa.text(
        'CREATE POLICY p_audit ON public."audit_logs" FOR SELECT TO authenticated '
        "USING (workspace_id IS NOT NULL AND public.is_member(workspace_id));"
    ))

    for table in _DENY_TABLES:
        op.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY;'))
        _drop_all_policies(table)

    op.execute(sa.text(_PROVISION_FN))
    op.execute(sa.text("NOTIFY pgrst, 'reload schema';"))


def downgrade() -> None:
    # This is a reconciliation migration: the helpers, policies, and provisioning
    # function all existed before this revision, and arbitrary pre-upgrade policy
    # state cannot be reconstructed safely.  Retain the hardened objects.  In
    # particular, dropping provision_me() here would corrupt the schema represented
    # by revision 0022 because that function was introduced by 0016.
    pass
