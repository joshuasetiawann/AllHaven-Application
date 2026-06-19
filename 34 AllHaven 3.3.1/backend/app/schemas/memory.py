"""Pydantic schemas for the AI Memory API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

MemoryCategory = Literal["Profile", "Preferences", "Projects", "Decisions", "Writing style", "Work context", "UI/UX preferences", "Technical", "Technical preferences", "Tasks context", "Finance context", "Goals", "Other"]
MemorySensitivity = Literal["LOW", "MEDIUM", "HIGH"]
MemoryStatus = Literal["active", "pending", "disabled", "stale"]


class MemoryCreate(BaseModel):
    category: MemoryCategory = "Profile"
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    sensitivity: MemorySensitivity = "LOW"


class MemoryUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = None
    category: Optional[MemoryCategory] = None


class MemoryOut(ORMModel):
    id: uuid.UUID
    category: str
    title: str
    content: str
    source: str
    status: str
    sensitivity: str
    enabled: bool
    confidence: float
    relevance_score: float
    last_used_at: Optional[datetime] = None
    source_session_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class SuggestionOut(ORMModel):
    id: uuid.UUID
    memory_id: Optional[uuid.UUID] = None
    category: str
    title: str
    content: str
    source_session_id: Optional[uuid.UUID] = None
    source_snippet: Optional[str] = None
    confidence: float
    sensitivity: str
    extraction_method: str
    status: str
    created_at: datetime


class MemorySettingsOut(BaseModel):
    auto_learning_enabled: bool
    require_approval_sensitive: bool


class MemorySettingsUpdate(BaseModel):
    auto_learning_enabled: Optional[bool] = None
    require_approval_sensitive: Optional[bool] = None
