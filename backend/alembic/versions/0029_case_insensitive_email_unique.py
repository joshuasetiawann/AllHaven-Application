"""Enforce case-insensitive identity-email uniqueness.

Revision ID: 0029_ci_email_unique
Revises: 0028_bearer_revocations
Create Date: 2026-08-13

The preflight is read-only and completes for both identity tables before any
index is created. Existing collisions abort without merging or deleting data.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_ci_email_unique"
down_revision: Union[str, None] = "0028_bearer_revocations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEXES = (
    ("local_users", "uq_local_users_email_ci"),
    ("profiles", "uq_profiles_email_ci"),
)


def _has_collision(bind, table: str) -> bool:
    # Select only a constant: neither output nor errors expose the address.
    statement = sa.text(
        f'SELECT 1 FROM "{table}" '
        'GROUP BY lower("email") HAVING count(*) > 1 LIMIT 1'
    )
    return bind.execute(statement).first() is not None


def upgrade() -> None:
    bind = op.get_bind()
    collisions = [_has_collision(bind, table) for table, _index in _INDEXES]
    if any(collisions):
        raise RuntimeError(
            "Case-insensitive identity email collisions must be resolved before upgrading."
        )

    for table, index in _INDEXES:
        op.create_index(index, table, [sa.text('lower("email")')], unique=True)


def downgrade() -> None:
    for table, index in reversed(_INDEXES):
        op.drop_index(index, table_name=table)
