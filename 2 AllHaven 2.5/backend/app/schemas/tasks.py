"""Task schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.domain.tasks import MAX_CHECKLIST_ITEMS, TASK_PRIORITIES, TASK_STATUSES
from app.schemas.common import ORMModel


def _validate_status(value: str) -> str:
    value = value.upper()
    if value not in TASK_STATUSES:
        raise ValueError(f"status must be one of {TASK_STATUSES}")
    return value


def _validate_priority(value: str) -> str:
    value = value.upper()
    if value not in TASK_PRIORITIES:
        raise ValueError(f"priority must be one of {TASK_PRIORITIES}")
    return value


class ChecklistItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class ChecklistItemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    is_done: Optional[bool] = None


class ChecklistItemOut(ORMModel):
    id: uuid.UUID
    title: str
    is_done: bool
    position: int


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    status: str = "TODO"
    priority: str = "NORMAL"
    due_at: Optional[datetime] = None
    # Optional checklist (max 5 items) created alongside the task.
    checklist: List[str] = Field(default_factory=list, max_length=MAX_CHECKLIST_ITEMS)

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        return _validate_status(v)

    @field_validator("priority")
    @classmethod
    def _priority(cls, v):
        return _validate_priority(v)

    @field_validator("checklist")
    @classmethod
    def _checklist(cls, v):
        cleaned = [t.strip() for t in (v or []) if t and t.strip()]
        if len(cleaned) > MAX_CHECKLIST_ITEMS:
            raise ValueError(f"A task can have at most {MAX_CHECKLIST_ITEMS} checklist items")
        return cleaned


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_at: Optional[datetime] = None

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        return _validate_status(v) if v is not None else v

    @field_validator("priority")
    @classmethod
    def _priority(cls, v):
        return _validate_priority(v) if v is not None else v


class TaskOut(ORMModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    checklist_items: List[ChecklistItemOut] = Field(default_factory=list)
