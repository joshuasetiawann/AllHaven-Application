"""Normalize SECURITY DEFINER function ownership at an immutable head.

Revision ID: 0027_function_owners
Revises: 0026_security_closure
Create Date: 2026-08-13

Revision 0026 now assigns each recreated helper/RPC function to the role running
the migration. Databases that recorded 0026 before that hardening still need an
additive revision which performs the same ownership reconciliation.
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_function_owners"
down_revision: Union[str, None] = "0026_security_closure"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FUNCTION_SIGNATURES = (
    "public.app_user_id()",
    "public.is_member(uuid)",
    "public.provision_me(text)",
)


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
            "auth.users table. Check the Supabase database URL."
        )
    return auth_users_exists


def upgrade() -> None:
    if not _is_supabase_target():
        return

    for signature in _FUNCTION_SIGNATURES:
        op.execute(sa.text(
            f"ALTER FUNCTION {signature} OWNER TO CURRENT_USER;"
        ))


def downgrade() -> None:
    # The prior owners are intentionally not retained: they may be untrusted,
    # and restoring arbitrary ownership would undo the security reconciliation.
    pass
