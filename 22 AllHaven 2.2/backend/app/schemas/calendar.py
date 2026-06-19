"""Calendar event schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)
    start_at: datetime
    end_at: Optional[datetime] = None
    all_day: bool = False


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    all_day: Optional[bool] = None


class CalendarEventOut(ORMModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_at: datetime
    end_at: Optional[datetime] = None
    all_day: bool
    created_at: datetime
    updated_at: datetime
