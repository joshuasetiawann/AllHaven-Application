"""Shared API dependencies.

``get_current_principal`` is the single authentication entry point. It accepts
either auth scheme and returns an immutable :class:`Principal`:

    * ``Authorization: Bearer <jwt>`` — programmatic/API clients and tools.
    * HttpOnly session cookie — the browser. State-changing methods must also
      send the ``X-CSRF-Token`` header matching the session's CSRF token
      (double-submit); bearer requests don't need CSRF (headers can't be set
      cross-site without passing CORS).

Routers and services never read ``workspace_id`` from the client.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.principal import Principal
from app.core.security import decode_access_token
from app.domain.users import LocalUser, Profile
from app.services import session_service
from app.services.auth_service import get_default_workspace

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _principal_for_user(db: Session, user_id: uuid.UUID) -> Principal:
    user = db.get(LocalUser, user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("Account is inactive or does not exist.")
    workspace = get_default_workspace(db, user.id)
    if not workspace:
        raise UnauthorizedError("No workspace found for this account.")
    profile = db.get(Profile, user.id)
    return Principal(
        user_id=user.id,
        workspace_id=workspace.id,
        email=user.email,
        full_name=profile.full_name if profile else None,
    )


def get_current_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    # 1) Bearer token (programmatic clients).
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            payload = decode_access_token(token)
        except ValueError as exc:
            raise UnauthorizedError("Invalid or expired token.") from exc
        subject = payload.get("sub")
        if not subject:
            raise UnauthorizedError("Invalid token.")
        try:
            user_id = uuid.UUID(str(subject))
        except (ValueError, TypeError) as exc:
            raise UnauthorizedError("Invalid token.") from exc
        return _principal_for_user(db, user_id)

    # 2) Session cookie (browser).
    session = session_service.validate_session(
        db, request.cookies.get(session_service.SESSION_COOKIE)
    )
    if session is None:
        raise UnauthorizedError("Authentication required.")
    if request.method not in _SAFE_METHODS:
        sent = request.headers.get(session_service.CSRF_HEADER, "")
        if not sent or sent != session.csrf_token:
            raise ForbiddenError("CSRF check failed. Refresh the page and try again.",
                                 error_code="CSRF_FAILED")
    return _principal_for_user(db, session.user_id)
