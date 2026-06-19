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
    meta: Optional[dict] = None
    created_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None
    provider_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    reply: MessageOut
    ai_configured: bool
    provider_id: Optional[str] = None
    blocked: bool = False


class MultiChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None
    # 1–3 agents. >3 fails validation (HTTP 422: "Maximum 3 agents per run").
    provider_ids: List[str] = Field(min_length=1, max_length=3)


class DebateChatRequest(BaseModel):
    """Multi-agent debate: 2–3 agents argue across rounds, then one synthesizes."""

    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None
    provider_ids: List[str] = Field(min_length=1, max_length=3)
    # Round 1 opening + rebuttal rounds. Bounded so a run can't explode in calls.
    rounds: int = Field(default=2, ge=1, le=4)


class ReasoningChatRequest(BaseModel):
    """Reasoning council: Analyst -> Critic -> Synthesizer with a quality gate."""

    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None
    provider_ids: List[str] = Field(min_length=1, max_length=3)
    # Depth + sampling: fast (1 pass), balanced (analyst+synthesizer), deep (+critic).
    mode: Literal["fast", "balanced", "deep"] = "balanced"


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
