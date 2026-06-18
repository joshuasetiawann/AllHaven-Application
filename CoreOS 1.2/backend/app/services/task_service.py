"""Task service: workspace-scoped CRUD with soft delete and audit logging."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.principal import Principal
from app.domain.tasks import MAX_CHECKLIST_ITEMS, Task, TaskChecklistItem
from app.schemas.tasks import ChecklistItemCreate, ChecklistItemUpdate, TaskCreate, TaskUpdate
from app.services.audit_service import snapshot, write_audit


def list_tasks(
    db: Session,
    principal: Principal,
    *,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Task]:
    stmt = select(Task).where(
        Task.workspace_id == principal.workspace_id,
        Task.is_deleted.is_(False),
    )
    if status:
        stmt = stmt.where(Task.status == status.upper())
    stmt = stmt.order_by(Task.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def get_task(db: Session, principal: Principal, task_id: uuid.UUID) -> Task:
    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.workspace_id == principal.workspace_id,
            Task.is_deleted.is_(False),
        )
    )
    if not task:
        raise NotFoundError("Task not found.")
    return task


def create_task(db: Session, principal: Principal, data: TaskCreate) -> Task:
    task = Task(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        title=data.title,
        description=data.description,
        status=data.status,
        priority=data.priority,
        due_at=data.due_at,
    )
    if task.status == "DONE":
        task.completed_at = datetime.now(timezone.utc)
    db.add(task)
    db.flush()

    for position, title in enumerate(data.checklist[:MAX_CHECKLIST_ITEMS]):
        db.add(
            TaskChecklistItem(
                task_id=task.id,
                workspace_id=principal.workspace_id,
                created_by=principal.user_id,
                title=title,
                position=position,
            )
        )

    write_audit(
        db,
        action="CREATE",
        entity_name="task",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=task.id,
        after=snapshot(task),
    )
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, principal: Principal, task_id: uuid.UUID, data: TaskUpdate) -> Task:
    task = get_task(db, principal, task_id)
    before = snapshot(task)

    fields = data.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(task, key, value)
    task.updated_by = principal.user_id

    if "status" in fields:
        if task.status == "DONE" and task.completed_at is None:
            task.completed_at = datetime.now(timezone.utc)
        elif task.status != "DONE":
            task.completed_at = None

    db.flush()
    write_audit(
        db,
        action="UPDATE",
        entity_name="task",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=task.id,
        before=before,
        after=snapshot(task),
    )
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, principal: Principal, task_id: uuid.UUID) -> None:
    task = get_task(db, principal, task_id)
    before = snapshot(task)
    task.is_deleted = True
    task.updated_by = principal.user_id
    db.flush()
    write_audit(
        db,
        action="DELETE",
        entity_name="task",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=task.id,
        before=before,
    )
    db.commit()


def set_completion(db: Session, principal: Principal, task_id: uuid.UUID, *, done: bool) -> Task:
    """Mark a task done (sets completed_at) or reopen it (clears completed_at)."""
    task = get_task(db, principal, task_id)
    task.status = "DONE" if done else "TODO"
    task.completed_at = datetime.now(timezone.utc) if done else None
    task.updated_by = principal.user_id
    db.flush()
    write_audit(
        db,
        action="COMPLETE" if done else "REOPEN",
        entity_name="task",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=task.id,
    )
    db.commit()
    db.refresh(task)
    return task


# --- Checklist items ------------------------------------------------------


def _get_item(db: Session, principal: Principal, task_id: uuid.UUID, item_id: uuid.UUID) -> TaskChecklistItem:
    item = db.scalar(
        select(TaskChecklistItem).where(
            TaskChecklistItem.id == item_id,
            TaskChecklistItem.task_id == task_id,
            TaskChecklistItem.workspace_id == principal.workspace_id,
        )
    )
    if not item:
        raise NotFoundError("Checklist item not found.")
    return item


def add_checklist_item(
    db: Session, principal: Principal, task_id: uuid.UUID, data: ChecklistItemCreate
) -> Task:
    task = get_task(db, principal, task_id)
    if len(task.checklist_items) >= MAX_CHECKLIST_ITEMS:
        raise BadRequestError(
            f"A task can have at most {MAX_CHECKLIST_ITEMS} checklist items.",
            error_code="CHECKLIST_LIMIT",
        )
    position = (max((i.position for i in task.checklist_items), default=-1)) + 1
    item = TaskChecklistItem(
        task_id=task.id,
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        title=data.title.strip(),
        position=position,
    )
    db.add(item)
    db.commit()
    db.refresh(task)
    return task


def update_checklist_item(
    db: Session,
    principal: Principal,
    task_id: uuid.UUID,
    item_id: uuid.UUID,
    data: ChecklistItemUpdate,
) -> Task:
    task = get_task(db, principal, task_id)
    item = _get_item(db, principal, task_id, item_id)
    fields = data.model_dump(exclude_unset=True)
    if "title" in fields and fields["title"]:
        item.title = fields["title"].strip()
    if "is_done" in fields and fields["is_done"] is not None:
        item.is_done = fields["is_done"]
    db.commit()
    db.refresh(task)
    return task


def delete_checklist_item(
    db: Session, principal: Principal, task_id: uuid.UUID, item_id: uuid.UUID
) -> Task:
    task = get_task(db, principal, task_id)
    item = _get_item(db, principal, task_id, item_id)
    db.delete(item)
    db.commit()
    db.refresh(task)
    return task
