"""Tasks router (thin: delegates to task_service)."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.tasks import (
    ChecklistItemCreate,
    ChecklistItemUpdate,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    tasks = task_service.list_tasks(db, principal, status=status, limit=limit, offset=offset)
    return success_response([TaskOut.model_validate(t) for t in tasks], "Tasks retrieved")


@router.post("")
def create_task(
    payload: TaskCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    task = task_service.create_task(db, principal, payload)
    return success_response(TaskOut.model_validate(task), "Task created")


@router.get("/{task_id}")
def get_task(
    task_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    task = task_service.get_task(db, principal, task_id)
    return success_response(TaskOut.model_validate(task), "Task retrieved")


@router.patch("/{task_id}")
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    task = task_service.update_task(db, principal, task_id, payload)
    return success_response(TaskOut.model_validate(task), "Task updated")


@router.delete("/{task_id}")
def delete_task(
    task_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    task_service.delete_task(db, principal, task_id)
    return success_response({"id": str(task_id)}, "Task deleted")


@router.post("/{task_id}/complete")
def complete_task(
    task_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    task = task_service.set_completion(db, principal, task_id, done=True)
    return success_response(TaskOut.model_validate(task), "Task completed")


@router.post("/{task_id}/reopen")
def reopen_task(
    task_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    task = task_service.set_completion(db, principal, task_id, done=False)
    return success_response(TaskOut.model_validate(task), "Task reopened")


@router.post("/{task_id}/checklist")
def add_checklist_item(
    task_id: uuid.UUID,
    payload: ChecklistItemCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    task = task_service.add_checklist_item(db, principal, task_id, payload)
    return success_response(TaskOut.model_validate(task), "Checklist item added")


@router.patch("/{task_id}/checklist/{item_id}")
def update_checklist_item(
    task_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ChecklistItemUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    task = task_service.update_checklist_item(db, principal, task_id, item_id, payload)
    return success_response(TaskOut.model_validate(task), "Checklist item updated")


@router.delete("/{task_id}/checklist/{item_id}")
def delete_checklist_item(
    task_id: uuid.UUID,
    item_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    task = task_service.delete_checklist_item(db, principal, task_id, item_id)
    return success_response(TaskOut.model_validate(task), "Checklist item deleted")
