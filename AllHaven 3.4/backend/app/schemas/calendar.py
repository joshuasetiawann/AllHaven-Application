"""Calendar event schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)
    start_at: datetime
    end_at: Optional[datetime] = None
    all_day: bool = False
    time_period: Optional[Literal["morning", "afternoon", "evening"]] = None
    repeat_rule: Literal["once", "daily", "weekly", "monthly"] = "once"
    repeat_days: Optional[list[str]] = None
    icon: Optional[str] = Field(default=None, max_length=32)
    color: Optional[str] = Field(default=None, max_length=32)


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    all_day: Optional[bool] = None
    time_period: Optional[Literal["morning", "afternoon", "evening"]] = None
    repeat_rule: Optional[Literal["once", "daily", "weekly", "monthly"]] = None
    repeat_days: Optional[list[str]] = None
    icon: Optional[str] = Field(default=None, max_length=32)
    color: Optional[str] = Field(default=None, max_length=32)


class CalendarEventOut(ORMModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_at: datetime
    end_at: Optional[datetime] = None
    all_day: bool
    time_period: Optional[str] = None
    repeat_rule: str = "once"
    repeat_days: Optional[list[str]] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    created_at: datetime
    updated_at: datetime
