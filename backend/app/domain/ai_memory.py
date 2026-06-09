# backend/app/domain/ai_memory.py
"""AI memory models: persistent memories, extraction suggestions, and conversation summaries."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

MEMORY_CATEGORIES = (
    "Profile", "Preferences", "Projects", "Decisions", "Writing style",
    "Work context", "UI/UX preferences", "Technical", "Technical preferences",
    "Tasks context", "Finance context", "Goals", "Other",
)
MEMORY_STATUSES = ("active", "pending", "disabled", "stale")
SENSITIVITY_LEVELS = ("LOW", "MEDIUM", "HIGH")
MEMORY_SOURCES = ("chat_extracted", "manual", "llm_extracted", "tool_result", "approved_action")
EXTRACTION_METHODS = ("rule_based", "llm")
SUGGESTION_STATUSES = ("pending", "approved", "rejected", "auto_saved")


class AiMemory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A persistent user memory, scoped to a workspace."""

    __tablename__ = "ai_memories"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="Profile")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    sensitivity: Mapped[str] = mapped_column(String(10), nullable=False, default="LOW")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONType, nullable=True)
    # Soft delete: a delete is an UPDATE (is_deleted=true) so two-way LWW sync carries it
    # in both directions instead of the row being resurrected from the peer on next pull.
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiMemorySuggestion(UUIDPrimaryKeyMixin, Base):
    """A memory candidate awaiting user approval.

    Carries updated_at so accept/reject status transitions sync across desktop +
    mobile (3.9: "Memory suggestions must sync across devices").
    """

    __tablename__ = "ai_memory_suggestions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    memory_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="Profile")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    source_snippet: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    sensitivity: Mapped[str] = mapped_column(String(10), nullable=False, default="LOW")
    extraction_method: Mapped[str] = mapped_column(String(20), nullable=False, default="rule_based")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AiConversationSummary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cached conversation summary, regenerated when message count grows significantly."""

    __tablename__ = "ai_conversation_summaries"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    message_count_at_summary: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
