"""Auth router: register, login, and current user."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.principal import Principal
from app.core.responses import success_response
from app.domain.users import Profile
from app.schemas.auth import LoginRequest, MeData, RegisterRequest, TokenData, UserOut, WorkspaceOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(principal_email: str, profile: Profile) -> UserOut:
    return UserOut(
        id=profile.id,
        email=principal_email,
        full_name=profile.full_name,
        created_at=profile.created_at,
    )


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    user, workspace = auth_service.register_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    profile = db.get(Profile, user.id)
    token = auth_service.issue_token(user)
    data = TokenData(access_token=token, user=_user_out(user.email, profile))
    return success_response(data, "Account created successfully")


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = auth_service.authenticate(db, email=payload.email, password=payload.password)
    if not user:
        # Generic message: never reveal whether the email or password was wrong.
        raise UnauthorizedError("Invalid email or password.", error_code="INVALID_CREDENTIALS")
    profile = db.get(Profile, user.id)
    token = auth_service.issue_token(user)
    data = TokenData(access_token=token, user=_user_out(user.email, profile))
    return success_response(data, "Logged in successfully")


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
