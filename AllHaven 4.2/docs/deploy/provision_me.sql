-- ===========================================================================
-- Deploy provision_me() to Supabase
-- ===========================================================================
-- Fixes: "Could not find the function public.provision_me(p_full_name) in the
-- schema cache" during mobile registration.
--
-- This is IDENTICAL to migration backend/alembic/versions/0016_provision_me.py.
-- Two ways to apply it:
--   1. Supabase Dashboard → SQL Editor → paste this whole file → Run.  (fastest)
--   2. From backend/, with DATABASE_URL pointed at Supabase:
--          ALLHAVEN_DB_TARGET=supabase alembic upgrade head
--
-- It is SECURITY DEFINER (bypasses RLS to provision a brand-new user's own
-- profile/workspace/membership) and idempotent (safe to run twice). It links an
-- existing same-email profile (desktop-first accounts) instead of duplicating.
-- The final NOTIFY makes PostgREST expose the RPC immediately.
-- ===========================================================================

drop function if exists public.provision_me(text);

create function public.provision_me(p_full_name text default null)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid uuid := auth.uid();
  v_email text;
  v_name text;
  v_profile_id uuid;
  v_ws_id uuid;
  v_created boolean := false;
begin
  if v_uid is null then
    raise exception 'not authenticated' using errcode = '28000';
  end if;

  -- Email + (fallback) display name from the auth user's signUp metadata.
  select email, raw_user_meta_data->>'full_name'
    into v_email, v_name from auth.users where id = v_uid;
  v_name := coalesce(nullif(p_full_name, ''), nullif(v_name, ''));

  -- 1) Profile: reuse by supabase_user_id; else adopt an unlinked same-email
  --    profile (desktop-first case); else create a fresh one.
  select id into v_profile_id from profiles where supabase_user_id = v_uid;
  if v_profile_id is null then
    select id into v_profile_id from profiles where email = v_email;
    if v_profile_id is null then
      v_profile_id := gen_random_uuid();
      insert into profiles (id, email, full_name, supabase_user_id, created_at, updated_at)
        values (v_profile_id, v_email, v_name, v_uid, now(), now());
      v_created := true;
    else
      update profiles
         set supabase_user_id = v_uid,
             full_name = coalesce(full_name, v_name),
             updated_at = now()
       where id = v_profile_id;
    end if;
  end if;

  -- 2) Workspace: ensure the user owns at least one.
  select id into v_ws_id from workspaces
    where owner_id = v_profile_id order by created_at asc limit 1;
  if v_ws_id is null then
    v_ws_id := gen_random_uuid();
    insert into workspaces (id, name, owner_id, created_at, updated_at)
      values (v_ws_id, coalesce(v_name || '''s Workspace', 'My Workspace'),
              v_profile_id, now(), now());
  end if;

  -- 3) Membership: ensure an owner row exists (no duplicates).
  insert into workspace_members (id, workspace_id, user_id, role, created_at, updated_at)
    select gen_random_uuid(), v_ws_id, v_profile_id, 'owner', now(), now()
    where not exists (
      select 1 from workspace_members
      where workspace_id = v_ws_id and user_id = v_profile_id
    );

  return jsonb_build_object(
    'status', 'success',
    'created', v_created,
    'profile_id', v_profile_id,
    'workspace_id', v_ws_id
  );
end;
$$;

revoke all on function public.provision_me(text) from public;
grant execute on function public.provision_me(text) to authenticated;

-- Make PostgREST expose the RPC right away (avoids the schema-cache miss).
notify pgrst, 'reload schema';
