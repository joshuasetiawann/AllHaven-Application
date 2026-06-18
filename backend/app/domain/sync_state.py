from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class SyncState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-(workspace, table, direction) incremental watermark/cursor. Local-only; never synced."""

    __tablename__ = "sync_state"
    __table_args__ = (
        UniqueConstraint("workspace_id", "table_name", "direction", name="uq_sync_state_ws_table_dir"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # "push" | "pull"
    last_value: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_pk: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
