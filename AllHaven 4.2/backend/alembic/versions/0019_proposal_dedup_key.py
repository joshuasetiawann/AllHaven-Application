"""transactions + calendar_events: add proposal-scoped dedup_key for cross-device dedup.

executed_at (0018) blocks a second approve once it syncs across desktop (Postgres) and
mobile (Supabase). The rare residual window is BOTH devices approving the same proposal
before executed_at propagates — each would insert a duplicate finance/routine row. The
executor now stamps every produced row with "{proposal_id}:{ordinal}"; a UNIQUE index
(NULLs distinct, so existing/manual rows are unaffected) plus a sync-time skip
(sync_engine.lww_apply) makes the two converge to one row.

Additive on both local Postgres and Supabase — run `alembic upgrade head` on BOTH.

Revision ID: 0019_proposal_dedup_key
Revises: 0018_proposal_idempotency
Create Date: 2026-06-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_proposal_dedup_key"
down_revision: Union[str, None] = "0018_proposal_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("transactions", "calendar_events")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("dedup_key", sa.String(length=80), nullable=True))
        op.create_index(f"uq_{table}_dedup_key", table, ["dedup_key"], unique=True)


def downgrade() -> None:
    for table in _TABLES:
        op.drop_index(f"uq_{table}_dedup_key", table_name=table)
        op.drop_column(table, "dedup_key")
