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
from app.schemas.tasks import TaskCreate, TaskOut, TaskUpdate
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
