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
    # Memory suggestions: same — accept/reject must sync across devices.
    op.add_column(
        "ai_memory_suggestions",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(sa.text("UPDATE ai_memory_suggestions SET updated_at = created_at"))

    # Stamp updated_at from the DB (server clock) on every UPDATE so LWW never mixes a
    # desktop server clock with a mobile phone wall clock. set_updated_at() (migration
    # 0012) preserves an explicitly-set value for sync-apply, so peers still converge.
    # Postgres only (no such trigger on the SQLite test DB).
    if op.get_bind().dialect.name == "postgresql":
        for table in ("ai_tool_proposals", "ai_memory_suggestions"):
            op.execute(sa.text(f'DROP TRIGGER IF EXISTS trg_set_updated_at ON "{table}";'))
            op.execute(sa.text(
                f'CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON "{table}" '
                f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
            ))


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in ("ai_tool_proposals", "ai_memory_suggestions"):
            op.execute(sa.text(f'DROP TRIGGER IF EXISTS trg_set_updated_at ON "{table}";'))
    op.drop_column("ai_memory_suggestions", "updated_at")
    op.drop_column("ai_tool_proposals", "updated_at")
    op.drop_column("ai_tool_proposals", "error_message")
