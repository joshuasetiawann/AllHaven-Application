# backend/alembic/versions/0015_workspace_members_rls_hardening.py
"""Restrict workspace_members RLS: SELECT-own only; writes reserved for service_role

The broad FOR ALL policy p_member on workspace_members (from 0013) allowed any
authenticated mobile client to INSERT a row for any workspace_id, which let them
call is_member(arbitrary_workspace) and gain read/write access to a stranger's
workspace data via the workspace-scoped policies.

Fix: drop the broad policy, replace with SELECT-only for authenticated.  With RLS
enabled and no INSERT/UPDATE/DELETE policy, Postgres DENIES writes for authenticated
users.  The backend (service_role) bypasses RLS and continues to manage memberships.

MVP has no team-invitation flow, so mobile clients have no legitimate write path to
workspace_members.

Revision ID: 0015_workspace_members_rls_hardening
Revises: 0014_sync_state
Create Date: 2026-06-19
"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_workspace_members_rls_hardening"
down_revision: Union[str, None] = "0014_sync_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enabled() -> bool:
    return os.getenv("ALLHAVEN_DB_TARGET", "").lower() == "supabase"


def upgrade() -> None:
    if not _enabled():
        return
    # Drop the broad FOR ALL policy that allowed privilege escalation via
    # self-insert into any workspace_id.
    op.execute(sa.text('DROP POLICY IF EXISTS p_member ON "workspace_members";'))
    # Replace with SELECT-only: authenticated users can only see rows they own.
    # No INSERT/UPDATE/DELETE policy → Postgres denies writes for authenticated.
    # service_role (backend) bypasses RLS and manages memberships exclusively.
    op.execute(sa.text(
        'CREATE POLICY p_member ON "workspace_members" FOR SELECT TO authenticated '
        "USING (user_id = app_user_id());"
    ))


def downgrade() -> None:
    if not _enabled():
        return
    # Restore the original FOR ALL policy from 0013 (reversible chain).
    op.execute(sa.text('DROP POLICY IF EXISTS p_member ON "workspace_members";'))
    op.execute(sa.text(
        'CREATE POLICY p_member ON "workspace_members" FOR ALL TO authenticated '
        "USING (user_id = app_user_id()) WITH CHECK (user_id = app_user_id());"
    ))
