"""Supabase Auth provisioning — create a GoTrue auth user for each AllHaven user.

Best-effort and never blocks the main flow: all failures are logged at debug and
never raised to callers. The service_role key and the user password are NEVER
logged or returned. Admin calls use the service_role key (not the anon key).
"""
from __future__ import annotations

import json
import logging
import threading
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
                        from app.services.config_common import secret_storage_context

                        key = decrypt_secret(
                            raw,
                            context=secret_storage_context(row, "service_role_key"),
                        )
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
        # An email collision does not prove this caller owns the existing remote
        # identity. Never look it up, reset its password, or return its id from an
        # account-creation attempt; an explicitly authenticated link is required.
        if exc.code in (409, 422):
            log.debug("Supabase create_user conflict")
            return None
        log.debug("Supabase create_user HTTP %s", exc.code)
        return None
    except Exception as exc:  # pragma: no cover - network defensive
        log.debug("Supabase create_user failed: %s", type(exc).__name__)
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
    from app.core.exceptions import AppException, ValidationAppError
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
    if not sb_id:
        # `create_user` intentionally hides remote response details so neither
        # credentials nor account-enumeration signals reach the client. This is
        # an explicit user action, however, so best-effort `None` must not be
        # wrapped in a successful API envelope.
        raise AppException(
            "Supabase Auth could not create or link this account. Verify the "
            "project URL and service role key, then try again.",
            status_code=502,
            error_code="SUPABASE_CONNECT_FAILED",
        )

    from app.domain.users import Profile

    profile = db.get(Profile, principal.user_id)
    if profile is None:
        raise AppException(
            "The local profile could not be linked to Supabase Auth.",
            status_code=500,
            error_code="SUPABASE_LINK_FAILED",
        )
    profile.supabase_user_id = sb_id
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        log.debug("Supabase profile link commit failed: %s", type(exc).__name__)
        raise AppException(
            "The Supabase account was created but the local profile link could not be saved.",
            status_code=500,
            error_code="SUPABASE_LINK_FAILED",
        ) from exc
    return {"connected": True}


def sync_password_now(db: Session, *, user_id, email: str, full_name, password: str) -> Optional[str]:
    """Keep one identity across desktop + mobile: ensure the Supabase Auth user
    exists, its password matches the desktop password, and the profile is linked.
    Returns the Supabase user id (or None). Best-effort — never raises. Synchronous
    core (the login path calls the async wrapper below so it never blocks)."""
    try:
        from app.domain.users import Profile

        url, key = get_service_credentials(db, workspace_id=None)
        if not url or not key:
            return None
        profile = db.get(Profile, user_id)
        existing = profile.supabase_user_id if profile is not None else None
        if existing:
            existing = str(existing)
            # Already linked → just keep the password in lock-step (one admin call).
            _set_user_password(url, key, existing, password)
            return existing
        # Not linked yet → create (idempotent) + link.
        sb_id = create_user(url, key, email=email, password=password, full_name=full_name)
        if sb_id and profile is not None:
            profile.supabase_user_id = sb_id
            db.commit()
        return sb_id
    except Exception:  # pragma: no cover - best-effort; must never affect login
        log.debug("Supabase password sync skipped")
        return None


def sync_password_async(user_id, email: str, full_name, password: str) -> None:
    """Fire-and-forget the password sync on a daemon thread (opens its own session)
    so a successful login returns immediately."""
    def _worker() -> None:
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            sync_password_now(db, user_id=user_id, email=email, full_name=full_name, password=password)
        finally:
            db.close()

    try:
        threading.Thread(target=_worker, daemon=True).start()
    except Exception:  # pragma: no cover - defensive
        pass


# --- Bridge auth: asymmetric (ES256) access tokens --------------------------
# Supabase projects created with asymmetric JWT signing keys sign user access
# tokens with ES256, which the stdlib-only HS256 verifier in core.security cannot
# check ("Unsupported token algorithm"). Rather than take on a native crypto
# dependency to validate JWKS, ask Supabase — it is authoritative for its own
# tokens and additionally rejects ones invalidated by a sign-out.
def verify_access_token(url: str, api_key: str, token: str) -> Optional[str]:
    """Return the Supabase user id for *token*, or None if Supabase rejects it.

    The token is never logged. Verification is authoritative on every request so
    a provider-side sign-out/revocation is honored immediately.
    """
    req = urllib.request.Request(
        f"{url.rstrip('/')}/auth/v1/user",
        headers={"apikey": api_key, "Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (fixed auth URL)
            user_id = json.loads(resp.read().decode() or "{}").get("id")
    except Exception as exc:
        log.debug("Supabase token verification failed: %s", exc)
        return None

    return str(user_id) if user_id else None
