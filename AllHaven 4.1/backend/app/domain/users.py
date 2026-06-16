"""User identity models.

``LocalUser`` exists only for the local MVP auth adapter and is isolated behind
the auth boundary (replaceable by Supabase Auth). ``Profile`` is the public
application profile linked to the authenticated user id.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base, GUID, TimestampMixin, UUIDPrimaryKeyMixin


class LocalUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Local-auth user record. Replaceable by an external auth provider."""

    __tablename__ = "local_users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Profile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Public profile linked 1:1 with a user id."""

    __tablename__ = "profiles"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    supabase_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), unique=True, nullable=True, index=True
    )
