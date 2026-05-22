"""Shared API dependencies.

``get_current_principal`` is the single authentication entry point. It reads the
bearer token, resolves the user and their default workspace, and returns an
immutable :class:`Principal`. Routers and services never read ``workspace_id``
from the client.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.principal import Principal
from app.core.security import decode_access_token
from app.domain.users import LocalUser, Profile
from app.services.auth_service import get_default_workspace


def get_current_principal(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Authentication required.")

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
