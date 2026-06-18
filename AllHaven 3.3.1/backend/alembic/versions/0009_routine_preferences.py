"""routine preferences and time slots

Revision ID: 0009_routine_preferences
Revises: 0008_ai_workspace_tools
Create Date: 2026-06-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_routine_preferences"
down_revision: Union[str, None] = "0008_ai_workspace_tools"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column("calendar_events", sa.Column("time_period", sa.String(length=16), nullable=True))
    op.add_column(
        "calendar_events",
        sa.Column("repeat_rule", sa.String(length=16), server_default="once", nullable=False),
    )
    op.add_column("calendar_events", sa.Column("repeat_days", _json_type(), nullable=True))
    op.add_column("calendar_events", sa.Column("icon", sa.String(length=32), nullable=True))
    op.add_column("calendar_events", sa.Column("color", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("calendar_events", "color")
    op.drop_column("calendar_events", "icon")
    op.drop_column("calendar_events", "repeat_days")
    op.drop_column("calendar_events", "repeat_rule")
    op.drop_column("calendar_events", "time_period")
