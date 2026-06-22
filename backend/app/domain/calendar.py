"""Local routine schedule events (workspace-scoped, MVP).

Routine events persist in the local PostgreSQL database and work without Google.
The old table name stays for compatibility with previous Calendar releases.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin


class CalendarEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "calendar_events"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    time_period: Mapped[str | None] = mapped_column(String(16), nullable=True)
    repeat_rule: Mapped[str] = mapped_column(String(16), default="once", nullable=False)
    repeat_days: Mapped[list[str] | None] = mapped_column(JSONType, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Cross-device idempotency: an approved proposal stamps "{proposal_id}:{ordinal}"
    # (one ordinal per event in a routine batch). UNIQUE (NULLs distinct) so the rare
    # pre-sync double-approve converges to one set of events. See sync_engine.lww_apply.
    dedup_key: Mapped[str | None] = mapped_column(String(80), nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("uq_calendar_events_dedup_key", "dedup_key", unique=True),
    )
