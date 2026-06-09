"""ai_memories: add is_deleted + deleted_at for durable, sync-safe deletes.

Deleting a memory used to be a HARD delete (db.delete). The two-way sync engine has no
delete-propagation: push only sends rows still present locally and pull re-inserts the
still-present remote row — so a memory deleted on desktop reappeared on the next sync
tick (the user-reported "I delete it, refresh, and it comes back"). Soft-delete turns the
delete into an UPDATE (is_deleted=true) that LWW sync carries in both directions, and all
reads filter is_deleted=false, so the deletion is durable and converges across devices.

Mirrors the tasks/notes pattern (is_deleted + deleted_at). Additive on both local
Postgres and Supabase — run `alembic upgrade head` on BOTH targets.

Revision ID: 0020_ai_memory_soft_delete
Revises: 0019_proposal_dedup_key
Create Date: 2026-06-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_ai_memory_soft_delete"
down_revision: Union[str, None] = "0019_proposal_dedup_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default false so existing rows backfill to "not deleted"; the ORM default
    # keeps new inserts correct without relying on the server default afterwards.
    op.add_column(
        "ai_memories",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "ai_memories",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ai_memories_is_deleted", "ai_memories", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_ai_memories_is_deleted", table_name="ai_memories")
    op.drop_column("ai_memories", "deleted_at")
    op.drop_column("ai_memories", "is_deleted")
