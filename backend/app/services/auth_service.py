"""Auth service: the local MVP auth boundary.

This is the single place that knows about local password auth. Swapping to
Supabase Auth later means replacing this module (and the dependency that reads
the token), not touching every router.
"""

from __future__ import annotations

import uuid
from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.users import LocalUser, Profile
from app.domain.workspaces import Workspace, WorkspaceMember
from app.services.audit_service import write_audit


# Missing and disabled accounts still perform one real PBKDF2 verification. A
# fixed salt avoids delaying every process startup while remaining unrelated to
# any real user's credentials.
_DUMMY_PASSWORD_HASH = (
    "pbkdf2_sha256$200000$YWxsaGF2ZW4tZHVtbXk=$"
    "67dd00/1o/ILmGgfqvTBU62tj//ReGbwy6UFvPAiLkE="
)


def get_user_by_email(db: Session, email: str) -> Optional[LocalUser]:
    return db.scalar(select(LocalUser).where(func.lower(LocalUser.email) == email.lower()))


def _get_profile_by_email(db: Session, email: str) -> Optional[Profile]:
    return db.scalar(select(Profile).where(func.lower(Profile.email) == email.lower()))


def _raise_registration_collision(db: Session, email: str) -> None:
    """Translate only verified identity races into stable public errors."""
    if get_user_by_email(db, email) is not None:
        raise ConflictError(
            "An account with this email already exists.",
            error_code="EMAIL_TAKEN",
        )
    if _get_profile_by_email(db, email) is not None:
        raise ConflictError(
            "This profile must be linked through a trusted authentication flow.",
            error_code="TRUSTED_LINK_REQUIRED",
        )


def get_default_workspace(db: Session, user_id: uuid.UUID) -> Optional[Workspace]:
    return db.scalar(
        select(Workspace).where(Workspace.owner_id == user_id).order_by(Workspace.created_at.asc())
    )


def _register_user_unchecked(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: Optional[str],
) -> Tuple[LocalUser, Workspace]:
    """Create a user, profile, default workspace, and owner membership."""
    # Friendly preflights avoid unnecessary password work in the common case;
    # the unique indexes plus the outer IntegrityError translation are the
    # authoritative race-safe guard.
    if get_user_by_email(db, email):
        raise ConflictError("An account with this email already exists.", error_code="EMAIL_TAKEN")
    if _get_profile_by_email(db, email) is not None:
        raise ConflictError(
            "This profile must be linked through a trusted authentication flow.",
            error_code="TRUSTED_LINK_REQUIRED",
        )

    user = LocalUser(email=email, hashed_password=hash_password(password))
    db.add(user)
    db.flush()  # assigns user.id

    profile = Profile(id=user.id, email=email, full_name=full_name)
    db.add(profile)

    workspace_name = f"{full_name}'s Workspace" if full_name else "My Workspace"
    workspace = Workspace(name=workspace_name, owner_id=user.id)
    db.add(workspace)
    db.flush()  # assigns workspace.id

    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))

    write_audit(
        db,
        action="CREATE",
        entity_name="local_user",
        workspace_id=workspace.id,
        user_id=user.id,
        entity_id=user.id,
        after={"email": email},
    )

    # Best-effort: provision a matching Supabase Auth user (env-level creds only at
    # signup — no workspace IntegrationConfig exists yet). Never blocks/raises.
    from app.services import supabase_auth_service

    sb_url, sb_key = supabase_auth_service.get_service_credentials(db, workspace_id=None)
    if sb_url and sb_key:
        sb_id = supabase_auth_service.create_user(
            sb_url, sb_key, email=email, password=password, full_name=full_name
        )
        if sb_id:
            profile.supabase_user_id = sb_id

    db.commit()
    db.refresh(user)
    db.refresh(workspace)
    return user, workspace


def register_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: Optional[str],
) -> Tuple[LocalUser, Workspace]:
    """Create one identity, translating concurrent email races safely."""
    try:
        return _register_user_unchecked(
            db,
            email=email,
            password=password,
            full_name=full_name,
        )
    except ConflictError:
        # The unchecked path may already have flushed work if the trusted-profile
        # guard trips; always return a clean session to FastAPI's dependency.
        db.rollback()
        raise
    except IntegrityError:
        # A competing transaction may win either case-insensitive identity index
        # after both requests complete their friendly preflight checks. Roll back
        # before reading the winner and never return raw SQL or password hashes.
        db.rollback()
        _raise_registration_collision(db, email)
        # An unrelated constraint failure remains a generic internal error.
        raise


def authenticate(db: Session, *, email: str, password: str) -> Optional[LocalUser]:
    """Return the user if credentials are valid, otherwise None."""
    user = get_user_by_email(db, email)
    usable = user is not None and user.is_active
    stored_hash = user.hashed_password if usable else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, stored_hash)
    return user if usable and password_matches else None


def issue_token(user: LocalUser) -> str:
    return create_access_token(str(user.id), extra_claims={"email": user.email})
