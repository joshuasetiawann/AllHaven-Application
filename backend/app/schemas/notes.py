"""Note schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


def _clean_tags(tags: Optional[List[str]]) -> List[str]:
    if not tags:
        return []
    cleaned = []
    for tag in tags:
        tag = (tag or "").strip()
        if tag and tag not in cleaned:
            cleaned.append(tag)
    return cleaned


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_pinned: bool = False

    @field_validator("tags")
    @classmethod
    def _tags(cls, v):
        return _clean_tags(v)


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    is_pinned: Optional[bool] = None

    @field_validator("tags")
    @classmethod
    def _tags(cls, v):
        return _clean_tags(v) if v is not None else v


class NoteOut(ORMModel):
    id: uuid.UUID
    title: str
    content: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_pinned: bool
    created_at: datetime
    updated_at: datetime
