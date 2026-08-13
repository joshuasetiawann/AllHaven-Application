"""Reconcile saved settings secrets to context-bound v3 envelopes.

Revision ID: 0024_secret_context
Revises: 0023_supabase_security
Create Date: 2026-08-13

This separate head is required for installations that had already recorded the
earlier one-time 0021 migration before v3 context binding was introduced.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.secrets import reencrypt_secret
from app.domain.base import GUID, JSONType

revision: str = "0024_secret_context"
down_revision: Union[str, None] = "0023_supabase_security"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _reconcile(table_name: str) -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table_name):
        return
    table = sa.table(
        table_name,
        sa.column("id", GUID()),
        sa.column("encrypted_secrets", JSONType),
    )
    for row in bind.execute(sa.select(table.c.id, table.c.encrypted_secrets)):
        values = dict(row.encrypted_secrets or {})
        changed = False
        for field, token in list(values.items()):
            if not isinstance(token, str) or not token:
                continue
            context = f"{table_name}:{row.id}:{field}"
            try:
                upgraded = reencrypt_secret(token, context=context)
            except ValueError as exc:
                raise RuntimeError(
                    f"Cannot rotate encrypted value in {table_name} row {row.id}, "
                    f"field {field}. Configure the prior key through "
                    "SETTINGS_ENCRYPTION_KEY_PREVIOUS and retry."
                ) from exc
            if upgraded != token:
                values[field] = upgraded
                changed = True
        if changed:
            bind.execute(
                table.update().where(table.c.id == row.id).values(encrypted_secrets=values)
            )


def upgrade() -> None:
    _reconcile("integration_configs")
    _reconcile("ai_agent_configs")


def downgrade() -> None:
    # Context-bound AEAD remains readable and must not be weakened on downgrade.
    pass
