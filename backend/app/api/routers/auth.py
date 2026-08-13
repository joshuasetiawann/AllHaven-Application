"""Auth router: register, login, refresh, logout, and current user.

Browser auth is an HttpOnly session cookie (+ CSRF cookie) set on login and
register, rotated by ``/auth/refresh``, and revoked server-side by
``/auth/logout``. The JSON response still carries a bearer token for
programmatic clients; the web frontend never stores it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.principal import Principal
from app.core.responses import success_response
from app.domain.users import Profile
from app.domain.workspaces import Workspace
from app.schemas.auth import (
    LoginRequest,
    MeData,
    MeUpdate,
    RegisterRequest,
    TokenData,
    UserOut,
    WorkspaceOut,
)
from app.services import auth_service, session_service, token_revocation_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(principal_email: str, profile: Profile) -> UserOut:
    return UserOut(
        id=profile.id,
        email=principal_email,
        full_name=profile.full_name,
        created_at=profile.created_at,
    )


def _login_response(db: Session, response: Response, user, profile: Profile, message: str) -> dict:
    """Issue the cookie session (browser) + bearer token (programmatic)."""
    session, raw = session_service.create_session(db, user.id)
    db.commit()
    session_service.set_session_cookies(response, raw, session.csrf_token)
    token = auth_service.issue_token(user)
    data = TokenData(access_token=token, user=_user_out(user.email, profile))
    return success_response(data, message)


@router.post("/register")
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    user, workspace = auth_service.register_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    profile = db.get(Profile, user.id)
    return _login_response(db, response, user, profile, "Account created successfully")


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    user = auth_service.authenticate(db, email=payload.email, password=payload.password)
    if not user:
        # Generic message: never reveal whether the email or password was wrong.
        raise UnauthorizedError("Invalid email or password.", error_code="INVALID_CREDENTIALS")
    profile = db.get(Profile, user.id)
    # One identity across desktop + mobile: keep the Supabase Auth password in
    # lock-step with the desktop password (background, best-effort) so mobile login
    # always works with the same credentials — no separate "Connect" step.
    from app.services import supabase_auth_service

    supabase_auth_service.sync_password_async(
        user.id, user.email, profile.full_name if profile else None, payload.password
    )
    return _login_response(db, response, user, profile, "Logged in successfully")


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    """Rotate the cookie session (new secrets, extended expiry).

    Requires a live session cookie AND the CSRF header — a cross-site page can
    neither read the CSRF cookie nor set the header, so it can't keep a victim's
    session alive or harvest fresh cookies.
    """
    current_raw = request.cookies.get(session_service.SESSION_COOKIE)
    sent = request.headers.get(session_service.CSRF_HEADER, "")
    rotated = session_service.rotate_session(db, current_raw, sent)
    if rotated is None:
        db.rollback()
        raise UnauthorizedError("Session refresh failed. Sign in again.")
    raw, csrf = rotated
    db.commit()
    session_service.set_session_cookies(response, raw, csrf)
    return success_response({"rotated": True}, "Session refreshed")


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    """Revoke cookie and/or bearer credentials, then clear browser cookies.

    Deliberately tolerant (no CSRF requirement): the worst a forged logout can
    do is sign the user out, and a reliable "get me out" matters more.
    """
    changed = False
    session = session_service.validate_session(
        db, request.cookies.get(session_service.SESSION_COOKIE)
    )
    if session is not None:
        session_service.revoke_session(db, session)
        changed = True

    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            # Validate before inserting so this deliberately CSRF-free escape
            # hatch cannot fill the database with arbitrary attacker input.
            get_current_principal(request, authorization, db)
        except UnauthorizedError:
            pass  # expired/already-revoked logout stays safely idempotent
        else:
            token_revocation_service.revoke(db, token)
            changed = True

    if changed:
        db.commit()
    session_service.clear_session_cookies(response)
    return success_response({"logged_out": True}, "Logged out")


@router.get("/me")
def me(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    profile = db.get(Profile, principal.user_id)
    workspace = auth_service.get_default_workspace(db, principal.user_id)
    data = MeData(
        user=_user_out(principal.email, profile),
        workspace=WorkspaceOut.model_validate(workspace),
    )
    return success_response(data, "Current user")


@router.patch("/me")
def update_me(
    payload: MeUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    profile = db.get(Profile, principal.user_id)
    workspace = auth_service.get_default_workspace(db, principal.user_id)
    fields = payload.model_dump(exclude_unset=True)
    if "full_name" in fields and profile is not None:
        profile.full_name = (fields["full_name"] or "").strip() or None
    if "workspace_name" in fields and workspace is not None:
        name = (fields["workspace_name"] or "").strip()
        if name:
            workspace.name = name
    db.commit()
    profile = db.get(Profile, principal.user_id)
    workspace = auth_service.get_default_workspace(db, principal.user_id)
    data = MeData(
        user=_user_out(principal.email, profile),
        workspace=WorkspaceOut.model_validate(workspace),
    )
    return success_response(data, "Profile updated")
