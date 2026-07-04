"""Audit log model. Append-only record of meaningful actions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, JSONType, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    before_data: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONType, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
