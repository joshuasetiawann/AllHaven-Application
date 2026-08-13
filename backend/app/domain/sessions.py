"""Browser session records for cookie-based authentication.

A session is an opaque secret delivered as an HttpOnly cookie. Only the SHA-256
hash of the secret is stored, so a database leak does not leak usable sessions.
Each session carries its own CSRF token (double-submit check on state-changing
requests) and is revocable server-side (logout) and rotatable (refresh).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("local_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SHA-256 hex of the opaque session secret (the raw secret is never stored).
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BearerTokenRevocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persistent deny-list entry for an exact bearer credential.

    Only a SHA-256 digest is retained.  The raw JWT/access token never reaches
    the database or application logs.  Entries expire with the credential and
    are pruned opportunistically by the revocation service.
    """

    __tablename__ = "bearer_token_revocations"

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
