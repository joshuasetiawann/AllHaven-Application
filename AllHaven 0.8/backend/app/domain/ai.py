"""AI models: chat sessions, chat messages, and tool proposals.

Tool proposals are the heart of the human-in-the-loop policy: the AI may only
*propose* an action (stored as PENDING). The MVP exposes listing and rejection;
it never auto-executes proposals (see AI_TOOL_POLICY.md).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

PROPOSAL_STATUSES = ("PENDING", "REJECTED", "EXPIRED")
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")


class ChatSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ChatMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "chat_messages"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Column name is "metadata" but the attribute is "meta" ("metadata" is reserved
    # by SQLAlchemy's declarative API).
    meta: Mapped[dict | None] = mapped_column("metadata", JSONType, nullable=True)
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

    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
