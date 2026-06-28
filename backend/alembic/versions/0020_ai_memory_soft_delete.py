"""ai_memories soft-delete columns

Revision ID: 0020_ai_memory_soft_delete
Revises: 0019_proposal_dedup_key
Create Date: 2026-06-28

This revision existed in live/local databases but the file was missing from the
repo, which made Alembic fail before the backend could start. Keep it idempotent
so databases that already have the columns can still upgrade cleanly.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_ai_memory_soft_delete"
down_revision: Union[str, None] = "0019_proposal_dedup_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    if not _has_column("ai_memories", "is_deleted"):
        op.add_column(
            "ai_memories",
            sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
        op.alter_column("ai_memories", "is_deleted", server_default=None)
    if not _has_column("ai_memories", "deleted_at"):
        op.add_column("ai_memories", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    if _has_column("ai_memories", "deleted_at"):
        op.drop_column("ai_memories", "deleted_at")
    if _has_column("ai_memories", "is_deleted"):
        op.drop_column("ai_memories", "is_deleted")
