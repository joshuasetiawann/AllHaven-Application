"""Supabase Auth provisioning — create a GoTrue auth user for each AllHaven user.

Best-effort and never blocks the main flow: all failures are logged at debug and
never raised to callers. The service_role key and the user password are NEVER
logged or returned. Admin calls use the service_role key (not the anon key).
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.supabase_sync_service import SUPABASE_PROVIDER_ID

log = logging.getLogger(__name__)


def get_service_credentials(
    db: Session, workspace_id: Optional[uuid.UUID]
) -> tuple[Optional[str], Optional[str]]:
    """Return (url, service_role_key): per-workspace IntegrationConfig first, then env."""
    if workspace_id is not None:
        from app.domain.integrations import IntegrationConfig

        row = db.scalar(
            select(IntegrationConfig).where(
                IntegrationConfig.workspace_id == workspace_id,
                IntegrationConfig.provider_id == SUPABASE_PROVIDER_ID,
                IntegrationConfig.enabled == True,  # noqa: E712
            )
        )
        if row:
            url = (row.public_config or {}).get("url") or ""
            key = ""
            if row.encrypted_secrets:
                try:
                    from app.core.secrets import decrypt_secret

                    raw = row.encrypted_secrets.get("service_role_key")
                    if raw:
                        key = decrypt_secret(raw)
                except Exception:  # pragma: no cover - defensive
                    key = ""
            if url and key:
                return url, key

    url = settings.SUPABASE_URL or ""
    key = settings.SUPABASE_SERVICE_ROLE_KEY or ""
    return (url or None, key or None)
