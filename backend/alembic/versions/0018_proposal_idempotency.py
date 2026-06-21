"""ai_tool_proposals: add executed_by + target_entity_id for cross-device idempotency.

A proposal can be approved on mobile (Supabase) and desktop (local Postgres) — two
databases bridged by LWW sync. executed_at already converges across them; these two
columns record WHO executed it and the entity it produced, so a second approval after
sync is blocked with a clear "already executed on another device" 409. Additive on
both local Postgres and Supabase — no enum/constraint/backfill changes.

Revision ID: 0018_proposal_idempotency
Revises: 0017_proposal_sync_fields
Create Date: 2026-06-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.domain.base import GUID

revision: str = "0018_proposal_idempotency"
down_revision: Union[str, None] = "0017_proposal_sync_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_tool_proposals", sa.Column("executed_by", GUID(), nullable=True))
    op.add_column("ai_tool_proposals", sa.Column("target_entity_id", GUID(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_tool_proposals", "target_entity_id")
    op.drop_column("ai_tool_proposals", "executed_by")
