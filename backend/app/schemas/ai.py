"""AI schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SessionCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)


class SessionOut(ORMModel):
    id: uuid.UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MessageOut(ORMModel):
    id: uuid.UUID
    session_id: Optional[uuid.UUID] = None
    role: str
    content: str
    meta: Optional[dict] = None
    created_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    reply: MessageOut
    ai_configured: bool


class ProposalOut(ORMModel):
    id: uuid.UUID
    tool_name: str
    tool_payload: dict
    status: str
    risk_level: str
    requires_confirmation: bool
    created_at: datetime
