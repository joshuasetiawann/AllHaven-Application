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


def create_user(
    url: str,
    service_role_key: str,
    *,
    email: str,
    password: str,
    full_name: Optional[str],
) -> Optional[str]:
    """Create a Supabase Auth user via GoTrue admin. Returns the new user id, or None.

    Best-effort: never raises, never logs the key/password.
    """
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"full_name": full_name} if full_name else {},
    }
    req = urllib.request.Request(
        f"{url.rstrip('/')}/auth/v1/admin/users",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
        sb_id = body.get("id")
        return str(sb_id) if sb_id else None
    except urllib.error.HTTPError as exc:
        # 422 user_already_exists is non-fatal (idempotent re-provision).
        log.debug("Supabase create_user HTTP %s", exc.code)
        return None
    except Exception as exc:  # pragma: no cover - network defensive
        log.debug("Supabase create_user failed: %s", type(exc).__name__)
        return None
