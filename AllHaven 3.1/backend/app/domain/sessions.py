"""Browser session records for cookie-based authentication.

A session is an opaque secret delivered as an HttpOnly cookie. Only the SHA-256
hash of the secret is stored, so a database leak does not leak usable sessions.
Each session carries its own CSRF token (double-submit check on state-changing
requests) and is revocable server-side (logout) and rotatable (refresh).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    # SHA-256 hex of the opaque session secret (the raw secret is never stored).
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
