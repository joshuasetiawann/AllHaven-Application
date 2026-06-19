# backend/alembic/versions/0017_proposal_sync_fields.py
"""ai_tool_proposals: add updated_at + error_message for cross-device status sync.

3.9: pending approvals must converge across desktop + mobile and failed approvals
must not disappear. `updated_at` lets the row take part in two-way LWW sync (so an
approve/reject on one device propagates), and `error_message` carries why a
FAILED/NEEDS_EDIT proposal didn't execute. Additive on both local Postgres and
Supabase — no enum/constraint changes.

Revision ID: 0017_proposal_sync_fields
Revises: 0016_provision_me
Create Date: 2026-06-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_proposal_sync_fields"
down_revision: Union[str, None] = "0016_provision_me"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_tool_proposals", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column(
        "ai_tool_proposals",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Backfill so existing rows have a sane watermark (= their creation time).
    op.execute(sa.text("UPDATE ai_tool_proposals SET updated_at = created_at"))


def downgrade() -> None:
    op.drop_column("ai_tool_proposals", "updated_at")
    op.drop_column("ai_tool_proposals", "error_message")
