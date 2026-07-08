"""AI models: chat sessions, chat messages, and tool proposals.

Tool proposals are the heart of the human-in-the-loop policy: the AI may only
*propose* a write action (stored as PENDING via the Tool Registry). A human then
approves (executed through the registry → service layer, status EXECUTED), edits,
or rejects it. Proposals are never executed in the model's turn
(see AI_TOOL_POLICY.md).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, JSONType, StringArray, TimestampMixin, UUIDPrimaryKeyMixin

PROPOSAL_STATUSES = ("PENDING", "NEEDS_EDIT", "APPROVED", "EXECUTED", "REJECTED", "FAILED", "EXPIRED")
# Statuses that still appear in the pending list (failed/needs-edit must not vanish).
PROPOSAL_OPEN_STATUSES = ("PENDING", "NEEDS_EDIT", "FAILED")
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")

# Multi-agent run statuses (the run aggregates per-agent results).
MULTI_RUN_STATUSES = ("running", "completed", "partial", "error", "empty")
# Per-agent response statuses (honest: blocked/not_configured/disabled are real).
AGENT_RESPONSE_STATUSES = (
    "queued", "running", "completed", "error", "not_configured", "disabled", "blocked",
    "unsupported",  # provider can't process an attached image (no vision)
)
MAX_AGENTS_PER_RUN = 10

# Default role per selection position in a multi-agent run. Each of the (up to 10)
# agents gets a distinct job; slot-level role overrides take precedence.
DEFAULT_AGENT_ROLES = (
    ("Main Assistant", "Understand the user's request and produce the primary answer."),
    ("Planner", "Break the request into concrete steps and propose a plan."),
    ("Research / Context", "Surface relevant facts, context, and data the others may miss."),
    ("Technical / Coder", "Handle code, architecture, debugging, and implementation detail."),
    ("Critic / Risk", "Find mistakes, risks, security issues, and weak assumptions."),
    ("Product / UX", "Improve usability, product logic, clarity, and user experience."),
    ("Data / Numbers", "Check totals, dates, quantities, and any structured data."),
    ("Scheduler", "Turn plans into realistic calendar/task next steps."),
    ("Creative / Tone", "Make the answer natural, readable, and matched to the user's style."),
    ("Synthesizer", "Merge everything into one polished, decisive final answer."),
)


class ChatGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A project/group that conversations can be organized into."""

    __tablename__ = "chat_groups"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class ChatSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Optional project/group the conversation belongs to.
    group_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    # Last active workspace section for this conversation (general/tasks/notes/...).
    section_key: Mapped[str] = mapped_column(String(50), nullable=False, default="general")


class ChatMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "chat_messages"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section_key: Mapped[str] = mapped_column(String(50), nullable=False, default="general", index=True)
    # Column name is "metadata" but the attribute is "meta" ("metadata" is reserved
    # by SQLAlchemy's declarative API).
    meta: Mapped[dict | None] = mapped_column("metadata", JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AiToolCall(UUIDPrimaryKeyMixin, Base):
    """Append-only audit rows for every model-requested tool call.

    This is separate from the general audit log so product/debug UI can inspect
    AI behavior without scraping unrelated audit events.
    """

    __tablename__ = "ai_tool_calls"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    message_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    access: Mapped[str | None] = mapped_column(String(20), nullable=True)
    arguments: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    result_preview: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AiMultiAgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single user message fanned out to up to 10 AI agents concurrently."""

    __tablename__ = "ai_multi_agent_runs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    user_message_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    provider_ids: Mapped[list[str]] = mapped_column(StringArray, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)


class AiAgentResponse(UUIDPrimaryKeyMixin, Base):
    """One agent's result within a multi-agent run. A failure here is isolated."""

    __tablename__ = "ai_agent_responses"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONType, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AiToolProposal(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_tool_proposals"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)

    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_payload: Mapped[dict] = mapped_column(JSONType, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="LOW")
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Why a FAILED/NEEDS_EDIT proposal didn't execute — shown in the pending panel.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Cross-device idempotency: a non-null executed_at is the authoritative "already
    # executed" signal (it converges across desktop/mobile via LWW sync); these record
    # who ran it and the entity it produced.
    executed_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # updated_at lets the proposal participate in two-way LWW sync, so a status change
    # (approve/reject on one device) converges across desktop + mobile.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
