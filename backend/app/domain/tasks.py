"""Task and checklist models. Workspace-scoped, soft-deleted, audited."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin

TASK_STATUSES = ("TODO", "IN_PROGRESS", "DONE")
TASK_PRIORITIES = ("LOW", "NORMAL", "HIGH", "URGENT")
MAX_CHECKLIST_ITEMS = 5


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="TODO")
    priority: Mapped[str] = mapped_column(String(30), nullable=False, default="NORMAL")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Checklist items are hard-deleted on removal, so this list always reflects
    # the active items (max 5, enforced in the service layer).
    checklist_items: Mapped[list["TaskChecklistItem"]] = relationship(
        "TaskChecklistItem",
        order_by="TaskChecklistItem.position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TaskChecklistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_checklist_items"

    task_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
