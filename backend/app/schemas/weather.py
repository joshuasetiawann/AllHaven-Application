"""Weather schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class WeatherLocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    is_default: bool = False


class WeatherLocationOut(ORMModel):
    id: uuid.UUID
    name: str
    is_default: bool
    created_at: datetime
