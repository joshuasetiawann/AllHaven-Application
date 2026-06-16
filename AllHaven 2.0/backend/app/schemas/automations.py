"""Automation definition schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AutomationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: Optional[str] = None
    trigger_type: str = Field(default="manual", max_length=60)
    action_type: str = Field(default="noop", max_length=60)
    config: dict = Field(default_factory=dict)


class AutomationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    description: Optional[str] = None
    trigger_type: Optional[str] = Field(default=None, max_length=60)
    action_type: Optional[str] = Field(default=None, max_length=60)
    config: Optional[dict] = None
    enabled: Optional[bool] = None


class AutomationOut(ORMModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    trigger_type: str
    action_type: str
    config: dict
    enabled: bool
    created_at: datetime
    updated_at: datetime
