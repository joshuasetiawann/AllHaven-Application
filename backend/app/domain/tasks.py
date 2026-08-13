"""Task and checklist models. Workspace-scoped, soft-deleted, audited."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin

TASK_STATUSES = ("TODO", "IN_PROGRESS", "DONE")
TASK_PRIORITIES = ("LOW", "NORMAL", "HIGH", "URGENT")
MAX_CHECKLIST_ITEMS = 5


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_tasks_workspace_id_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="TODO")
    priority: Mapped[str] = mapped_column(String(30), nullable=False, default="NORMAL")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Checklist items are soft-deleted (is_deleted=True) on removal; this
    # relationship filters tombstones so only ACTIVE items are visible to the
    # desktop API. MAX_CHECKLIST_ITEMS cap and position math therefore ignore
    # tombstones automatically.
    checklist_items: Mapped[list["TaskChecklistItem"]] = relationship(
        "TaskChecklistItem",
        primaryjoin=(
            "and_(Task.id == foreign(TaskChecklistItem.task_id), "
            "Task.workspace_id == foreign(TaskChecklistItem.workspace_id), "
            "TaskChecklistItem.is_deleted == False)"
        ),
        order_by="TaskChecklistItem.position",
        cascade="all, delete-orphan",
        lazy="selectin",
        viewonly=False,
    )


class TaskChecklistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_checklist_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "task_id"],
            ["tasks.workspace_id", "tasks.id"],
            name="fk_task_checklist_items_workspace_task_id_tasks",
            ondelete="CASCADE",
        ),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
