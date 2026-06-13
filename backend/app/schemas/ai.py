"""AI schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SessionCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    group_id: Optional[uuid.UUID] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    # group_id may be set to a group, or explicitly null to remove from a group.
    group_id: Optional[uuid.UUID] = None


class SessionOut(ORMModel):
    id: uuid.UUID
    title: Optional[str] = None
    group_id: Optional[uuid.UUID] = None
    section_key: str = "general"
    created_at: datetime
    updated_at: datetime


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class GroupUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class GroupOut(ORMModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime


class MessageOut(ORMModel):
    id: uuid.UUID
    session_id: Optional[uuid.UUID] = None
    role: str
    content: str
    section_key: str = "general"
    meta: Optional[dict] = None
    created_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None
    provider_id: Optional[str] = None
    section_key: Optional[str] = Field(default="general", max_length=50)
    thinking_mode: Literal["fast", "balance", "thinking", "deep"] = "balance"
    response_language: Optional[str] = Field(default=None, max_length=24)


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    reply: MessageOut
    ai_configured: bool
    provider_id: Optional[str] = None
    blocked: bool = False


# Up to 4 image data URLs (data:image/...;base64,...) attached to a chat turn.
ImageList = Optional[List[str]]
# Thinking Mode: reasoning depth + sampling, separate from the chat mode.
ThinkingMode = Literal["fast", "balance", "thinking", "deep"]


class MultiChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None
    # 1-10 agents. Higher values fail validation before any provider call starts.
    provider_ids: List[str] = Field(min_length=1, max_length=10)
    images: ImageList = Field(default=None, max_length=4)
    thinking_mode: ThinkingMode = "balance"
    section_key: Optional[str] = Field(default="general", max_length=50)
    response_language: Optional[str] = Field(default=None, max_length=24)


class DebateChatRequest(BaseModel):
    """Multi-agent debate: up to 10 agents argue across rounds, then one synthesizes."""

    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None
    provider_ids: List[str] = Field(min_length=1, max_length=10)
    # Round 1 opening + rebuttal rounds. Bounded so a run can't explode in calls.
    rounds: int = Field(default=2, ge=1, le=4)
    images: ImageList = Field(default=None, max_length=4)
    thinking_mode: ThinkingMode = "balance"
    section_key: Optional[str] = Field(default="general", max_length=50)
    response_language: Optional[str] = Field(default=None, max_length=24)


class ReasoningChatRequest(BaseModel):
    """Reasoning council: Analyst -> Critic -> Synthesizer with a quality gate."""

    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None
    provider_ids: List[str] = Field(min_length=1, max_length=10)
    images: ImageList = Field(default=None, max_length=4)
    # Depth + sampling: fast (1 pass), balance (analyst+synth), thinking/deep (+critic).
    thinking_mode: ThinkingMode = "balance"
    section_key: Optional[str] = Field(default="general", max_length=50)
    response_language: Optional[str] = Field(default=None, max_length=24)


class AgentResponseOut(ORMModel):
    id: uuid.UUID
    run_id: uuid.UUID
    provider_id: str
    provider_name: str
    status: str
    content: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: Optional[int] = None
    meta: Optional[dict] = None
    created_at: datetime


class MultiChatResponse(BaseModel):
    run_id: uuid.UUID
    session_id: uuid.UUID
    status: str
    agent_responses: List[AgentResponseOut]


class ProposalOut(ORMModel):
    id: uuid.UUID
    tool_name: str
    tool_payload: dict
    status: str
    risk_level: str
    requires_confirmation: bool
    created_at: datetime
