"""Repeatable, transactional rotation of persisted settings secrets."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secrets import reencrypt_secret, secret_needs_reencryption
from app.domain.integrations import AiAgentConfig, IntegrationConfig
from app.services.config_common import secret_storage_context


SECRET_MODELS = (IntegrationConfig, AiAgentConfig)


def rotate_saved_secrets(db: Session, *, dry_run: bool = False) -> dict[str, int]:
    """Verify and rotate all config ciphertext under the current key.

    Operators set the new key as ``SETTINGS_ENCRYPTION_KEY`` and old key(s) as
    ``SETTINGS_ENCRYPTION_KEY_PREVIOUS`` before running this function. Any
    undecryptable value aborts and rolls back the entire operation.
    """
    scanned = 0
    rotated = 0
    rows_changed = 0
    try:
        for model in SECRET_MODELS:
            for row in db.scalars(select(model)).all():
                values = dict(row.encrypted_secrets or {})
                changed = False
                for field, token in list(values.items()):
                    if not isinstance(token, str) or not token:
                        continue
                    scanned += 1
                    context = secret_storage_context(row, field)
                    if secret_needs_reencryption(token, context=context):
                        values[field] = reencrypt_secret(token, context=context)
                        rotated += 1
                        changed = True
                if changed:
                    rows_changed += 1
                    if not dry_run:
                        row.encrypted_secrets = values
        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise
    return {"scanned": scanned, "rotated": rotated, "rows_changed": rows_changed}
