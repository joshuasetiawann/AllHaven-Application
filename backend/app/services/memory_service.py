# backend/app/services/memory_service.py
"""Memory CRUD: create, read, update, delete memories and approval suggestions.

All operations are workspace-scoped. The model never directly queries this table;
it uses tools from the Tool Registry which call these functions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.principal import Principal
from app.domain.ai_memory import AiMemory, AiMemorySuggestion

MAX_MEMORIES_PER_WORKSPACE = 500
MAX_SUGGESTIONS_PENDING = 50


# --------------------------------------------------------------------------- #
# memory CRUD
# --------------------------------------------------------------------------- #

def list_memories(
    db: Session,
    principal: Principal,
    *,
    category: Optional[str] = None,
    status: str = "active",
    enabled_only: bool = False,
    limit: int = 100,
) -> List[AiMemory]:
    stmt = select(AiMemory).where(
        AiMemory.workspace_id == principal.workspace_id,
        AiMemory.status == status,
    )
    if category:
        stmt = stmt.where(AiMemory.category == category)
    if enabled_only:
        stmt = stmt.where(AiMemory.enabled == True)  # noqa: E712
    stmt = stmt.order_by(AiMemory.updated_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def search_memories(db: Session, principal: Principal, query: str, limit: int = 20) -> List[AiMemory]:
    q = query.lower().strip()
    if not q:
        return []
    stmt = (
        select(AiMemory)
        .where(
            AiMemory.workspace_id == principal.workspace_id,
            AiMemory.status == "active",
            AiMemory.enabled == True,  # noqa: E712
            or_(
                func.lower(AiMemory.title).contains(q),
                func.lower(AiMemory.content).contains(q),
            ),
        )
        .order_by(AiMemory.relevance_score.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def get_memories_by_category(
    db: Session, principal: Principal, category: str
) -> List[AiMemory]:
    return list_memories(db, principal, category=category, enabled_only=True)


def get_memory(db: Session, principal: Principal, memory_id: uuid.UUID) -> AiMemory:
    m = db.scalar(
        select(AiMemory).where(
            AiMemory.id == memory_id,
            AiMemory.workspace_id == principal.workspace_id,
        )
    )
    if not m:
        raise NotFoundError("Memory not found.")
    return m


def create_memory(
    db: Session,
    principal: Principal,
    *,
    category: str,
    title: str,
    content: str,
    source: str = "manual",
    sensitivity: str = "LOW",
    confidence: float = 1.0,
    source_session_id: Optional[uuid.UUID] = None,
) -> AiMemory:
    count = db.scalar(
        select(func.count()).where(
            AiMemory.workspace_id == principal.workspace_id,
            AiMemory.status == "active",
        )
    ) or 0
    if count >= MAX_MEMORIES_PER_WORKSPACE:
        raise ValidationAppError(f"Workspace memory limit ({MAX_MEMORIES_PER_WORKSPACE}) reached. Delete old memories first.")

    m = AiMemory(
        workspace_id=principal.workspace_id,
        category=category,
        title=title[:200],
        content=content,
        source=source,
        sensitivity=sensitivity,
        confidence=confidence,
        source_session_id=source_session_id,
        status="active",
        enabled=True,
    )
    db.add(m)
    db.flush()
    return m


def update_memory(
    db: Session,
    principal: Principal,
    memory_id: uuid.UUID,
    *,
    title: Optional[str] = None,
    content: Optional[str] = None,
    category: Optional[str] = None,
    enabled: Optional[bool] = None,
    status: Optional[str] = None,
) -> AiMemory:
    m = get_memory(db, principal, memory_id)
    if title is not None:
        m.title = title[:200]
    if content is not None:
        m.content = content
    if category is not None:
        m.category = category
    if enabled is not None:
        m.enabled = enabled
    if status is not None:
        m.status = status
    db.flush()
    return m


def delete_memory(db: Session, principal: Principal, memory_id: uuid.UUID) -> None:
    m = get_memory(db, principal, memory_id)
    db.delete(m)
    db.flush()


def mark_used(db: Session, principal: Principal, memory_id: uuid.UUID) -> None:
    """Update last_used_at + bump relevance_score (called when memory was retrieved for context)."""
    m = db.scalar(
        select(AiMemory).where(
            AiMemory.id == memory_id,
            AiMemory.workspace_id == principal.workspace_id,
        )
    )
    if m:
        m.last_used_at = datetime.now(timezone.utc)
        m.relevance_score = min(1.0, m.relevance_score + 0.05)
        db.flush()


# --------------------------------------------------------------------------- #
# deduplication + upsert
# --------------------------------------------------------------------------- #

def find_existing_memory(
    db: Session, principal: Principal, category: str, title: str
) -> Optional[AiMemory]:
    """Find an active memory in the same category with a similar title (for dedup)."""
    title_lower = title.lower().strip()
    candidates = list_memories(db, principal, category=category, limit=50)
    for m in candidates:
        if m.title.lower().strip() == title_lower:
            return m
    return None


def upsert_memory(
    db: Session,
    principal: Principal,
    *,
    category: str,
    title: str,
    content: str,
    source: str = "chat_extracted",
    sensitivity: str = "LOW",
    confidence: float = 0.9,
    source_session_id: Optional[uuid.UUID] = None,
) -> AiMemory:
    """Create memory or update existing one with same category+title."""
    existing = find_existing_memory(db, principal, category, title)
    if existing:
        existing.content = content
        existing.confidence = max(existing.confidence, confidence)
        existing.source = source
        existing.status = "active"
        existing.enabled = True
        db.flush()
        return existing
    return create_memory(
        db, principal,
        category=category, title=title, content=content,
        source=source, sensitivity=sensitivity, confidence=confidence,
        source_session_id=source_session_id,
    )


# --------------------------------------------------------------------------- #
# suggestions
# --------------------------------------------------------------------------- #

def list_suggestions(
    db: Session, principal: Principal, status: str = "pending"
) -> List[AiMemorySuggestion]:
    stmt = (
        select(AiMemorySuggestion)
        .where(
            AiMemorySuggestion.workspace_id == principal.workspace_id,
            AiMemorySuggestion.status == status,
        )
        .order_by(AiMemorySuggestion.created_at.desc())
        .limit(MAX_SUGGESTIONS_PENDING)
    )
    return list(db.scalars(stmt).all())


def create_suggestion(
    db: Session,
    principal: Principal,
    *,
    category: str,
    title: str,
    content: str,
    source_session_id: Optional[uuid.UUID],
    source_snippet: str,
    confidence: float,
    sensitivity: str,
    extraction_method: str = "rule_based",
    memory_id: Optional[uuid.UUID] = None,
) -> AiMemorySuggestion:
    # Skip if identical pending suggestion already exists.
    existing = db.scalar(
        select(AiMemorySuggestion).where(
            AiMemorySuggestion.workspace_id == principal.workspace_id,
            AiMemorySuggestion.title == title[:200],
            AiMemorySuggestion.status == "pending",
        )
    )
    if existing:
        return existing
    s = AiMemorySuggestion(
        workspace_id=principal.workspace_id,
        memory_id=memory_id,
        category=category,
        title=title[:200],
        content=content,
        source_session_id=source_session_id,
        source_snippet=source_snippet[:500],
        confidence=confidence,
        sensitivity=sensitivity,
        extraction_method=extraction_method,
        status="pending",
    )
    db.add(s)
    db.flush()
    return s


def approve_suggestion(
    db: Session, principal: Principal, suggestion_id: uuid.UUID
) -> AiMemory:
    s = db.scalar(
        select(AiMemorySuggestion).where(
            AiMemorySuggestion.id == suggestion_id,
            AiMemorySuggestion.workspace_id == principal.workspace_id,
        )
    )
    if not s:
        raise NotFoundError("Suggestion not found.")
    if s.status != "pending":
        raise ValidationAppError(f"Suggestion is already {s.status}.")
    memory = upsert_memory(
        db, principal,
        category=s.category, title=s.title, content=s.content,
        source="manual", sensitivity=s.sensitivity, confidence=s.confidence,
        source_session_id=s.source_session_id,
    )
    s.status = "approved"
    s.memory_id = memory.id
    db.flush()
    return memory


def reject_suggestion(db: Session, principal: Principal, suggestion_id: uuid.UUID) -> None:
    s = db.scalar(
        select(AiMemorySuggestion).where(
            AiMemorySuggestion.id == suggestion_id,
            AiMemorySuggestion.workspace_id == principal.workspace_id,
        )
    )
    if not s:
        raise NotFoundError("Suggestion not found.")
    s.status = "rejected"
    db.flush()
