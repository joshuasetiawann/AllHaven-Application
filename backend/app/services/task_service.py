"""Task service: workspace-scoped CRUD with soft delete and audit logging."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.principal import Principal
from app.domain.tasks import Task
from app.schemas.tasks import TaskCreate, TaskUpdate
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
