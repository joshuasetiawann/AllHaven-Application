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
        # User already exists (409/422): locate it and reset its password so login
        # works, then return its id so the caller links the profile (idempotent).
        # Without this, a pre-existing auth user (e.g. created in the dashboard)
        # leaves profiles.supabase_user_id unset and mobile login can't resolve it.
        if exc.code in (409, 422):
            uid = _find_user_id_by_email(url, service_role_key, email)
            if uid:
                _set_user_password(url, service_role_key, uid, password)
                return uid
        log.debug("Supabase create_user HTTP %s", exc.code)
        return None
    except Exception as exc:  # pragma: no cover - network defensive
        log.debug("Supabase create_user failed: %s", type(exc).__name__)
        return None


def _find_user_id_by_email(url: str, service_role_key: str, email: str) -> Optional[str]:
    """GET the admin users list and return the id whose email matches, or None."""
    req = urllib.request.Request(
        f"{url.rstrip('/')}/auth/v1/admin/users",
        headers={"apikey": service_role_key, "Authorization": f"Bearer {service_role_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (fixed admin URL)
            data = json.loads(resp.read().decode() or "{}")
    except Exception as exc:  # pragma: no cover - network defensive
        log.debug("Supabase list users failed: %s", type(exc).__name__)
        return None
    users = data.get("users", []) if isinstance(data, dict) else []
    for u in users:
        if (u.get("email") or "").lower() == email.lower():
            uid = u.get("id")
            return str(uid) if uid else None
    return None


def _set_user_password(url: str, service_role_key: str, user_id: str, password: str) -> None:
    """Best-effort: reset an existing auth user's password (PUT admin/users/{id})."""
    req = urllib.request.Request(
        f"{url.rstrip('/')}/auth/v1/admin/users/{user_id}",
        data=json.dumps({"password": password, "email_confirm": True}).encode(),
        headers={
            "Content-Type": "application/json",
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):  # noqa: S310 (fixed admin URL)
            pass
    except Exception as exc:  # pragma: no cover - network defensive
        log.debug("Supabase set password failed: %s", type(exc).__name__)


def connect(db: Session, principal, password: str) -> dict:
    """Re-verify the user's password, then provision their Supabase Auth user."""
    from app.core.exceptions import ValidationAppError
    from app.services import auth_service

    user = auth_service.authenticate(db, email=principal.email, password=password)
    if not user:
        raise ValidationAppError("Incorrect password.", error_code="INVALID_PASSWORD")

    url, key = get_service_credentials(db, principal.workspace_id)
    if not url or not key:
        raise ValidationAppError(
            "Supabase service role key is not configured.", error_code="SUPABASE_NOT_CONFIGURED"
        )

    sb_id = create_user(
        url, key, email=principal.email, password=password, full_name=principal.full_name
    )
    if sb_id:
        from app.domain.users import Profile

        profile = db.get(Profile, principal.user_id)
        if profile is not None:
            profile.supabase_user_id = sb_id
            db.commit()
    return {"connected": bool(sb_id)}
