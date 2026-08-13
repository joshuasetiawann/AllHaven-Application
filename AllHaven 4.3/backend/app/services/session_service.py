"""Cookie session management: create, validate, rotate, revoke.

The browser auth path. An opaque secret (never stored raw — only its SHA-256
hash) rides in an HttpOnly cookie; a per-session CSRF token rides in a readable
cookie and must be echoed in the ``X-CSRF-Token`` header on state-changing
requests (double-submit). Logout revokes server-side; refresh rotates both
secrets so a leaked old cookie dies on first rotation.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.sessions import UserSession

SESSION_COOKIE = "allhaven_session"
CSRF_COOKIE = "allhaven_csrf"
CSRF_HEADER = "x-csrf-token"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expiry() -> datetime:
    return _now() + timedelta(days=settings.SESSION_TTL_DAYS)


def create_session(db: Session, user_id: uuid.UUID) -> tuple[UserSession, str]:
    """Create a session row; returns (row, raw_secret). Caller sets cookies."""
    raw = secrets.token_urlsafe(32)
    row = UserSession(
        user_id=user_id,
        token_hash=_hash(raw),
        csrf_token=secrets.token_urlsafe(24),
        expires_at=_expiry(),
    )
    db.add(row)
    db.flush()
    return row, raw


def validate_session(db: Session, raw: Optional[str]) -> Optional[UserSession]:
    """Resolve a raw cookie secret to a live session (or None, honestly)."""
    if not raw:
        return None
    row = db.scalar(select(UserSession).where(UserSession.token_hash == _hash(raw)))
    if row is None or row.revoked_at is not None:
        return None
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires < _now():
        return None
    return row


def rotate_session(
    db: Session,
    current_raw: Optional[str],
    current_csrf: str,
) -> Optional[tuple[str, str]]:
    """Atomically consume the old cookie and return the new secret pair.

    Validation and rotation happen in one compare-and-swap UPDATE. If two
    requests present the same cookie, only the first update can match.
    """
    if not current_raw or not current_csrf:
        return None

    raw = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    now = _now()
    result = db.execute(
        update(UserSession)
        .where(
            UserSession.token_hash == _hash(current_raw),
            UserSession.csrf_token == current_csrf,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at >= now,
        )
        .values(
            token_hash=_hash(raw),
            csrf_token=csrf,
            expires_at=now + timedelta(days=settings.SESSION_TTL_DAYS),
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        return None
    return raw, csrf


def revoke_session(db: Session, row: UserSession) -> None:
    row.revoked_at = _now()
    db.flush()


# --- cookie helpers ---------------------------------------------------------


def set_session_cookies(response: Response, raw: str, csrf_token: str) -> None:
    """Set the HttpOnly session cookie + the JS-readable CSRF cookie."""
    secure = not settings.is_local_env  # localhost dev runs over http
    max_age = settings.SESSION_TTL_DAYS * 24 * 3600
    response.set_cookie(
        SESSION_COOKIE, raw,
        max_age=max_age, httponly=True, secure=secure, samesite="lax", path="/",
    )
    # Not HttpOnly by design: the frontend reads it to send the CSRF header.
    response.set_cookie(
        CSRF_COOKIE, csrf_token,
        max_age=max_age, httponly=False, secure=secure, samesite="lax", path="/",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
