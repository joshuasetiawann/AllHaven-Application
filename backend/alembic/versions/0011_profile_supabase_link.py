"""profiles.supabase_user_id mapping to Supabase Auth

Revision ID: 0011_profile_supabase_link
Revises: 0010_soft_delete_deleted_at
Create Date: 2026-06-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from app.domain.base import GUID

revision: str = "0011_profile_supabase_link"
down_revision: Union[str, None] = "0010_soft_delete_deleted_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("supabase_user_id", GUID(), nullable=True))
    # ORM declares unique=True + index=True, which SQLAlchemy folds into ONE unique
    # index (ix_profiles_supabase_user_id) — mirror that exactly to avoid autogenerate drift.
    op.create_index("ix_profiles_supabase_user_id", "profiles", ["supabase_user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_profiles_supabase_user_id", table_name="profiles")
    op.drop_column("profiles", "supabase_user_id")
