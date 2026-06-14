"""Schemas for AI routine generation and atomic batch creation."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.calendar import CalendarEventCreate

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RoutineGenerateRequest(BaseModel):
    prompt: str = Field(default="", max_length=2000)
    date: str = Field(description="Target day as YYYY-MM-DD.")
    period: Literal["morning", "afternoon", "evening"] = "morning"
    use_context: bool = True

    @field_validator("date")
    @classmethod
    def _valid_date(cls, value: str) -> str:
        if not _DATE_RE.match(value):
            raise ValueError("date must be in YYYY-MM-DD format.")
        return value


class RoutineBatchCreate(BaseModel):
    items: list[CalendarEventCreate] = Field(min_length=1, max_length=50)
