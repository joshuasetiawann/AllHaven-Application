"""Task schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.domain.tasks import TASK_PRIORITIES, TASK_STATUSES
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


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    status: str = "TODO"
    priority: str = "NORMAL"
    due_at: Optional[datetime] = None

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        return _validate_status(v)

    @field_validator("priority")
    @classmethod
    def _priority(cls, v):
        return _validate_priority(v)


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
