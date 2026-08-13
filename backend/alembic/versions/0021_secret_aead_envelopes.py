"""Migrate saved integration secrets to versioned AES-GCM envelopes.

Revision ID: 0021_secret_aead_envelopes
Revises: 0020_ai_memory_soft_delete
Create Date: 2026-08-13

The application can still read the legacy format during rolling upgrades. This
migration rewrites every decryptable value with the current encryption key. It
fails closed, without printing ciphertext or plaintext, if a value cannot be
decrypted; operators can then provide the old key through
SETTINGS_ENCRYPTION_KEY_PREVIOUS and retry.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.secrets import reencrypt_secret
from app.domain.base import GUID, JSONType

revision: str = "0021_secret_aead_envelopes"
down_revision: Union[str, None] = "0020_ai_memory_soft_delete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _migrate_table(table_name: str) -> None:
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
            try:
                upgraded = reencrypt_secret(
                    token, context=f"{table_name}:{row.id}:{field}"
                )
            except ValueError as exc:
                raise RuntimeError(
                    f"Cannot migrate encrypted value in {table_name} row {row.id}, field {field}. "
                    "Add the old key to SETTINGS_ENCRYPTION_KEY_PREVIOUS and retry."
                ) from exc
            if upgraded != token:
                values[field] = upgraded
                changed = True
        if changed:
            bind.execute(
                table.update().where(table.c.id == row.id).values(encrypted_secrets=values)
            )


def upgrade() -> None:
    _migrate_table("integration_configs")
    _migrate_table("ai_agent_configs")


def downgrade() -> None:
    # AES-GCM envelopes remain readable by the application. Reintroducing the
    # custom legacy cipher on downgrade would weaken data at rest.
    pass
