# backend/alembic/versions/0016_provision_me.py
"""provision_me(): self-service account provisioning for mobile (Supabase-only)

Mobile registers directly against Supabase (no backend reachable). RLS has a
chicken-and-egg: a brand-new user can't INSERT their own profile because
p_self's WITH CHECK is `id = app_user_id()`, and app_user_id() resolves through
a profile row that doesn't exist yet. This adds a SECURITY DEFINER RPC the client
calls right after sign-in to provision profile + workspace + owner membership,
bypassing RLS safely. It is idempotent and also LINKS an existing same-email
profile (the desktop-first case), repairing the old "supabase_user_id null →
login fails" bug for accounts created on desktop first.

Guarded by ALLHAVEN_DB_TARGET=supabase (references auth.uid()/auth.users, which
only exist on Supabase — running it on the local Postgres would fail).

Revision ID: 0016_provision_me
Revises: 0015_workspace_members_rls
Create Date: 2026-06-19
"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_provision_me"
down_revision: Union[str, None] = "0015_workspace_members_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROVISION_FN = """
CREATE OR REPLACE FUNCTION public.provision_me(p_full_name text DEFAULT NULL)
RETURNS uuid
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
  v_ws_name text;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'not authenticated';
  END IF;

  -- Email + (fallback) display name from the auth user's signUp metadata.
  SELECT email, raw_user_meta_data->>'full_name'
    INTO v_email, v_name FROM auth.users WHERE id = v_uid;
  v_name := COALESCE(NULLIF(p_full_name, ''), NULLIF(v_name, ''));

  -- 1) Profile: reuse by supabase_user_id; else adopt an unlinked same-email
  --    profile (desktop-first case); else create a fresh one.
  SELECT id INTO v_profile_id FROM profiles WHERE supabase_user_id = v_uid;
  IF v_profile_id IS NULL THEN
    SELECT id INTO v_profile_id FROM profiles WHERE email = v_email;
    IF v_profile_id IS NULL THEN
      v_profile_id := gen_random_uuid();
      INSERT INTO profiles (id, email, full_name, supabase_user_id, created_at, updated_at)
        VALUES (v_profile_id, v_email, v_name, v_uid, now(), now());
    ELSE
      UPDATE profiles
         SET supabase_user_id = v_uid,
             full_name = COALESCE(full_name, v_name)
       WHERE id = v_profile_id;
    END IF;
  END IF;

  -- 2) Workspace: ensure the user owns at least one.
  SELECT id INTO v_ws_id FROM workspaces
    WHERE owner_id = v_profile_id ORDER BY created_at ASC LIMIT 1;
  IF v_ws_id IS NULL THEN
    v_ws_name := COALESCE(v_name || '''s Workspace', 'My Workspace');
    v_ws_id := gen_random_uuid();
    INSERT INTO workspaces (id, name, owner_id, created_at, updated_at)
      VALUES (v_ws_id, v_ws_name, v_profile_id, now(), now());
  END IF;

  -- 3) Membership: ensure an owner row exists (no duplicates).
  INSERT INTO workspace_members (id, workspace_id, user_id, role, created_at, updated_at)
    SELECT gen_random_uuid(), v_ws_id, v_profile_id, 'owner', now(), now()
    WHERE NOT EXISTS (
      SELECT 1 FROM workspace_members
      WHERE workspace_id = v_ws_id AND user_id = v_profile_id
    );

  RETURN v_profile_id;
END;
$$;

REVOKE ALL ON FUNCTION public.provision_me(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.provision_me(text) TO authenticated;
"""


def _enabled() -> bool:
    return os.getenv("ALLHAVEN_DB_TARGET", "").lower() == "supabase"


def upgrade() -> None:
    if not _enabled():
        return
    op.execute(sa.text(_PROVISION_FN))


def downgrade() -> None:
    if not _enabled():
        return
    op.execute(sa.text("DROP FUNCTION IF EXISTS public.provision_me(text);"))
