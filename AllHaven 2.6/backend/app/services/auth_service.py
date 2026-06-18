"""Auth service: the local MVP auth boundary.

This is the single place that knows about local password auth. Swapping to
Supabase Auth later means replacing this module (and the dependency that reads
the token), not touching every router.
"""

from __future__ import annotations

import uuid
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.users import LocalUser, Profile
from app.domain.workspaces import Workspace, WorkspaceMember
from app.services.audit_service import write_audit


def get_user_by_email(db: Session, email: str) -> Optional[LocalUser]:
    return db.scalar(select(LocalUser).where(LocalUser.email == email))


def get_default_workspace(db: Session, user_id: uuid.UUID) -> Optional[Workspace]:
    return db.scalar(
        select(Workspace).where(Workspace.owner_id == user_id).order_by(Workspace.created_at.asc())
    )


def register_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: Optional[str],
) -> Tuple[LocalUser, Workspace]:
    """Create a user, profile, default workspace, and owner membership."""
    if get_user_by_email(db, email):
        raise ConflictError("An account with this email already exists.", error_code="EMAIL_TAKEN")

    user = LocalUser(email=email, hashed_password=hash_password(password))
    db.add(user)
    db.flush()  # assigns user.id

    profile = Profile(id=user.id, email=email, full_name=full_name)
    db.add(profile)

    workspace_name = f"{full_name}'s Workspace" if full_name else "My Workspace"
    workspace = Workspace(name=workspace_name, owner_id=user.id)
    db.add(workspace)
    db.flush()  # assigns workspace.id

    membership = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    db.add(membership)

    write_audit(
        db,
        action="CREATE",
        entity_name="local_user",
        workspace_id=workspace.id,
        user_id=user.id,
        entity_id=user.id,
        after={"email": email},
    )

    db.commit()
    db.refresh(user)
    db.refresh(workspace)
    return user, workspace


def authenticate(db: Session, *, email: str, password: str) -> Optional[LocalUser]:
    """Return the user if credentials are valid, otherwise None."""
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def issue_token(user: LocalUser) -> str:
    return create_access_token(str(user.id), extra_claims={"email": user.email})
