"""Persist bearer-token revocations.

Revision ID: 0028_bearer_revocations
Revises: 0027_function_owners
Create Date: 2026-08-13
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.domain.base import GUID

revision: str = "0028_bearer_revocations"
down_revision: Union[str, None] = "0027_function_owners"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bearer_token_revocations",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bearer_token_revocations"),
    )
    op.create_index(
        "ix_bearer_token_revocations_token_hash",
        "bearer_token_revocations",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_bearer_token_revocations_expires_at",
        "bearer_token_revocations",
        ["expires_at"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql" and bool(
        bind.execute(sa.text("SELECT to_regclass('auth.users') IS NOT NULL")).scalar_one()
    ):
        # Backend-only security state: authenticated PostgREST users get no
        # policy and therefore cannot enumerate even token digests.
        op.execute(
            sa.text(
                'ALTER TABLE public."bearer_token_revocations" ENABLE ROW LEVEL SECURITY;'
            )
        )


def downgrade() -> None:
    op.drop_index(
        "ix_bearer_token_revocations_expires_at",
        table_name="bearer_token_revocations",
    )
    op.drop_index(
        "ix_bearer_token_revocations_token_hash",
        table_name="bearer_token_revocations",
    )
    op.drop_table("bearer_token_revocations")
