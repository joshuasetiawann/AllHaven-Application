# AI Memory System & Safe Database Access — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent, auto-learning memory system to AllHaven's AI chat so the AI remembers user context across sessions and can access all app data through the existing safe Tool Registry.

**Architecture:** A standalone `MemoryService` layer with its own DB tables (`ai_memories`, `ai_memory_suggestions`, `ai_conversation_summaries`). All 4 chat services (single, multi, debate, reasoning) inject a memory context block before sending to the model, and trigger hybrid extraction (rule-based inline → LLM daemon thread) after each response. Memory tools are added to the existing Tool Registry so the AI can explicitly query memories.

**Tech Stack:** FastAPI + SQLAlchemy 2.x + Alembic + PostgreSQL (backend); Next.js 14 + TypeScript + Tailwind (frontend).

---

## File Map

### New Backend Files
| File | Responsibility |
|------|---------------|
| `backend/app/domain/ai_memory.py` | SQLAlchemy models: AiMemory, AiMemorySuggestion, AiConversationSummary |
| `backend/alembic/versions/0007_ai_memories.py` | Migration: creates 3 new tables |
| `backend/app/schemas/memory.py` | Pydantic I/O schemas for memory endpoints |
| `backend/app/services/memory_service.py` | CRUD: create/read/update/delete memories + suggestions |
| `backend/app/services/memory_context_builder.py` | Builds prompt context block from memories |
| `backend/app/services/memory_extraction_service.py` | Hybrid extraction: rule-based + LLM background thread |
| `backend/app/services/supabase_sync_service.py` | Optional Supabase background sync |
| `backend/app/api/routers/memory.py` | REST endpoints: /ai/memory/* |

### Modified Backend Files
| File | Change |
|------|--------|
| `backend/app/domain/__init__.py` | Import ai_memory module |
| `backend/app/schemas/ai.py` | Add `section_key: Optional[str]` to all ChatRequest schemas |
| `backend/app/services/ai_orchestrator.py` | Accept `extra_context` param, inject into system prompt |
| `backend/app/services/ai_service.py` | Inject context before, trigger extraction after `chat()` |
| `backend/app/services/ai_multi_service.py` | Same for `multi_chat()` |
| `backend/app/services/ai_debate_service.py` | Same for `debate_chat()` |
| `backend/app/services/ai_reasoning_service.py` | Same for `reasoning_chat()` |
| `backend/app/services/ai_tools_registry.py` | Add 6 memory tools (3 read + 3 write) |
| `backend/app/services/ai_settings_service.py` | Add memory auto-learning settings |
| `backend/app/api/routers/ai.py` | Pass `section_key` from request to service calls |
| `backend/app/main.py` | Include memory router |

### New Frontend Files
| File | Responsibility |
|------|---------------|
| `frontend/app/dashboard/ai/memory/page.tsx` | Memory management page |
| `frontend/components/ai/MemoryIndicator.tsx` | Subtle in-chat indicator after extraction |

### Modified Frontend Files
| File | Change |
|------|--------|
| `frontend/types/index.ts` | Add AiMemory, MemorySuggestion, MemorySettings types |
| `frontend/lib/api.ts` | Add memoryApi; extend aiApi chat methods with section_key |
| `frontend/app/dashboard/ai/page.tsx` | Add MemoryIndicator; send section_key in chat calls |
| `frontend/components/layout/nav.ts` | Add AI Memory nav link |

---

## Task 1: Domain Models

**Files:**
- Create: `backend/app/domain/ai_memory.py`

- [ ] **Step 1.1: Create the domain models file**

```python
# backend/app/domain/ai_memory.py
"""AI memory models: persistent memories, extraction suggestions, and conversation summaries."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

MEMORY_CATEGORIES = ("Profile", "Preferences", "Projects", "WorkStyle", "Technical", "Goals")
MEMORY_STATUSES = ("active", "pending", "disabled", "stale")
SENSITIVITY_LEVELS = ("LOW", "MEDIUM", "HIGH")
MEMORY_SOURCES = ("chat_extracted", "manual", "llm_extracted")
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


class AiMemorySuggestion(UUIDPrimaryKeyMixin, Base):
    """A memory candidate awaiting user approval (sensitive or low-confidence extractions)."""

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


class AiConversationSummary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cached conversation summary, regenerated when message count grows significantly."""

    __tablename__ = "ai_conversation_summaries"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    message_count_at_summary: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

- [ ] **Step 1.2: Register the new models in domain __init__**

Read `backend/app/domain/__init__.py`. It currently contains just `"""AllHaven domain models."""` or similar. Add the import:

```python
# backend/app/domain/__init__.py
"""AllHaven domain models — imported here so SQLAlchemy metadata is complete."""

import app.domain.ai  # noqa: F401
import app.domain.ai_memory  # noqa: F401
import app.domain.audit  # noqa: F401
import app.domain.automations  # noqa: F401
import app.domain.calendar  # noqa: F401
import app.domain.files  # noqa: F401
import app.domain.finance  # noqa: F401
import app.domain.integrations  # noqa: F401
import app.domain.notes  # noqa: F401
import app.domain.sessions  # noqa: F401
import app.domain.tasks  # noqa: F401
import app.domain.users  # noqa: F401
import app.domain.weather  # noqa: F401
import app.domain.workspaces  # noqa: F401
```

---

## Task 2: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/0007_ai_memories.py`

- [ ] **Step 2.1: Create the migration**

```python
# backend/alembic/versions/0007_ai_memories.py
"""ai_memories, ai_memory_suggestions, ai_conversation_summaries

Revision ID: 0007_ai_memories
Revises: 0006_user_sessions
Create Date: 2026-06-12

Adds:
    * ai_memories               (persistent user memories scoped to workspace)
    * ai_memory_suggestions     (pending approval for extracted memory candidates)
    * ai_conversation_summaries (cached per-session summaries)

Existing tables/data are untouched. Reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.domain.base import GUID

revision: str = "0007_ai_memories"
down_revision: Union[str, None] = "0006_user_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_memories",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("category", sa.String(length=50), server_default=sa.text("'Profile'"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=30), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("sensitivity", sa.String(length=10), server_default=sa.text("'LOW'"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default=sa.text("1.0"), nullable=False),
        sa.Column("relevance_score", sa.Float(), server_default=sa.text("0.5"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_session_id", GUID(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_memories"),
    )
    op.create_index("ix_ai_memories_workspace_id", "ai_memories", ["workspace_id"])

    op.create_table(
        "ai_memory_suggestions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("memory_id", GUID(), nullable=True),
        sa.Column("category", sa.String(length=50), server_default=sa.text("'Profile'"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_session_id", GUID(), nullable=True),
        sa.Column("source_snippet", sa.String(length=500), nullable=True),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.8"), nullable=False),
        sa.Column("sensitivity", sa.String(length=10), server_default=sa.text("'LOW'"), nullable=False),
        sa.Column("extraction_method", sa.String(length=20), server_default=sa.text("'rule_based'"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_memory_suggestions"),
    )
    op.create_index("ix_ai_memory_suggestions_workspace_id", "ai_memory_suggestions", ["workspace_id"])

    op.create_table(
        "ai_conversation_summaries",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("workspace_id", GUID(), nullable=False),
        sa.Column("session_id", GUID(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("message_count_at_summary", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_conversation_summaries"),
        sa.UniqueConstraint("session_id", name="uq_ai_conversation_summaries_session_id"),
    )
    op.create_index("ix_ai_conversation_summaries_workspace_id", "ai_conversation_summaries", ["workspace_id"])
    op.create_index("ix_ai_conversation_summaries_session_id", "ai_conversation_summaries", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_conversation_summaries_session_id", table_name="ai_conversation_summaries")
    op.drop_index("ix_ai_conversation_summaries_workspace_id", table_name="ai_conversation_summaries")
    op.drop_table("ai_conversation_summaries")
    op.drop_index("ix_ai_memory_suggestions_workspace_id", table_name="ai_memory_suggestions")
    op.drop_table("ai_memory_suggestions")
    op.drop_index("ix_ai_memories_workspace_id", table_name="ai_memories")
    op.drop_table("ai_memories")
```

- [ ] **Step 2.2: Run the migration**

```bash
cd /mnt/storage/VSCode/Repo/AllHaven-Application/backend
python -m alembic upgrade head
```

Expected output ends with: `Running upgrade 0006_user_sessions -> 0007_ai_memories`

---

## Task 3: Memory Service (CRUD)

**Files:**
- Create: `backend/app/services/memory_service.py`

- [ ] **Step 3.1: Create the memory service**

```python
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
```

---

## Task 4: Memory Extraction Service

**Files:**
- Create: `backend/app/services/memory_extraction_service.py`

- [ ] **Step 4.1: Create the extraction service**

```python
# backend/app/services/memory_extraction_service.py
"""Hybrid memory extraction: rule-based (inline) + LLM (daemon thread, non-blocking).

Rule-based extraction fires synchronously with zero latency.
LLM extraction runs in a daemon thread only when rule-based finds ambiguous patterns.
Secret patterns are detected and NEVER saved — they're silently dropped.
"""
from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.principal import Principal

# --------------------------------------------------------------------------- #
# Secret detection — ALWAYS run before saving anything
# --------------------------------------------------------------------------- #

_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r'\bsk-[A-Za-z0-9_-]{12,}\b'),            # OpenAI-style keys
    re.compile(r'\b(?:gsk|pk|rk|xoxb|xoxp|ghp|gho|github_pat)_[A-Za-z0-9_-]{8,}\b'),
    re.compile(r'\bAKIA[0-9A-Z]{16}\b'),                  # AWS access key
    re.compile(r'\bBearer\s+[A-Za-z0-9._-]{12,}\b', re.IGNORECASE),
    re.compile(r'\beyJ[A-Za-z0-9._-]{20,}\b'),            # JWT
    re.compile(r'\b[A-Za-z0-9_-]{40,}\b'),                # long opaque tokens
    re.compile(
        r'\b(api[_-]?key|secret|token|password|passwd|pwd|authorization)\b\s*[:=]\s*\S+',
        re.IGNORECASE,
    ),
]


def _contains_secret(text: str) -> bool:
    for pat in _SECRET_PATTERNS:
        if pat.search(text):
            return True
    return False


# --------------------------------------------------------------------------- #
# Memory candidate
# --------------------------------------------------------------------------- #

@dataclass
class MemoryCandidate:
    category: str       # "Profile" | "Preferences" | "Projects" | ...
    title: str
    content: str
    confidence: float   # 0.0–1.0
    sensitivity: str    # "LOW" | "MEDIUM" | "HIGH"
    snippet: str        # the raw phrase that triggered this


# --------------------------------------------------------------------------- #
# Rule-based extraction patterns
# --------------------------------------------------------------------------- #

# Each entry: (compiled_regex, category, title_template, content_template, confidence, sensitivity)
# Capture group 1 is always the extracted value.
_RULES: list[tuple] = [
    # Name
    (re.compile(r'nama\s+saya\s+(?:adalah\s+)?([A-Za-z][A-Za-z\s]{1,40}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User name", "User's name is {value}.", 0.95, "LOW"),
    (re.compile(r'saya\s+bernama\s+([A-Za-z][A-Za-z\s]{1,40}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User name", "User's name is {value}.", 0.95, "LOW"),
    (re.compile(r'panggil\s+(?:saya|aku)\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User name", "User prefers to be called {value}.", 0.9, "LOW"),
    (re.compile(r'my\s+name\s+is\s+([A-Za-z][A-Za-z\s]{1,40}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User name", "User's name is {value}.", 0.95, "LOW"),

    # Role / job
    (re.compile(r'saya\s+(?:adalah\s+)?(?:seorang\s+)?([A-Za-z][A-Za-z\s]{1,50}?)\s+(?:di|pada|yang|bekerja)', re.IGNORECASE),
     "Profile", "User role", "User's role is {value}.", 0.75, "LOW"),
    (re.compile(r'(?:jabatan|posisi|pekerjaan)\s+saya\s+(?:adalah\s+)?([A-Za-z][A-Za-z\s]{1,50}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User role", "User's role is {value}.", 0.85, "LOW"),
    (re.compile(r'bekerja\s+sebagai\s+([A-Za-z][A-Za-z\s]{1,50}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User role", "User's role is {value}.", 0.85, "LOW"),
    (re.compile(r'i\s+(?:am|work\s+as)\s+(?:a\s+|an\s+)?([A-Za-z][A-Za-z\s]{1,50}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User role", "User's role is {value}.", 0.8, "LOW"),

    # Project
    (re.compile(r'project\s+(?:saya|kami|ini|utama\s+saya)\s+(?:adalah\s+|bernama\s+)?([A-Za-z0-9][A-Za-z0-9\s/_-]{1,60}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Projects", "Current project name", "User's current project is {value}.", 0.9, "LOW"),
    (re.compile(r'(?:sedang\s+)?(?:mengerjakan|membangun|membuat|develop)\s+(?:project\s+)?(?:bernama\s+|yang\s+namanya\s+)?([A-Za-z0-9][A-Za-z0-9\s/_-]{1,60}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Projects", "Current project name", "User is building a project called {value}.", 0.8, "LOW"),
    (re.compile(r'(?:this\s+)?project\s+(?:is\s+called\s+|named\s+|name\s+is\s+)([A-Za-z0-9][A-Za-z0-9\s/_-]{1,60}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Projects", "Current project name", "User's current project is {value}.", 0.9, "LOW"),

    # Response preferences
    (re.compile(r'saya\s+suka\s+jawaban\s+(?:yang\s+)?([A-Za-z][A-Za-z\s,]{2,80}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Preferences", "Response style preference", "User prefers {value} responses.", 0.9, "LOW"),
    (re.compile(r'(?:tolong\s+)?jawab\s+(?:dengan\s+)?(?:cara\s+)?(?:yang\s+)?([A-Za-z][A-Za-z\s,]{2,60}?)(?:\s+ya)?(?:[.,!?]|$)', re.IGNORECASE),
     "Preferences", "Response style preference", "User prefers {value} responses.", 0.75, "LOW"),
    (re.compile(r'jangan\s+(?:pernah\s+)?([A-Za-z][A-Za-z\s]{2,60}?)\s+(?:dalam\s+jawaban|ketika\s+menjawab)', re.IGNORECASE),
     "Preferences", "Response style - avoid", "User dislikes {value} in responses.", 0.85, "LOW"),
    (re.compile(r'i\s+(?:prefer|like|want)\s+(?:responses?\s+(?:that\s+are\s+|to\s+be\s+))?([A-Za-z][A-Za-z\s,]{2,80}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Preferences", "Response style preference", "User prefers {value} responses.", 0.85, "LOW"),

    # Tech stack
    (re.compile(r'(?:saya\s+)?(?:menggunakan|pakai|pake)\s+([A-Za-z0-9][A-Za-z0-9\s+_/-]{1,60}?)\s+(?:sebagai\s+)?(?:untuk|framework|library|tech\s+stack)', re.IGNORECASE),
     "Technical", "Tech stack", "User uses {value}.", 0.8, "LOW"),
    (re.compile(r'tech\s+stack\s+(?:saya\s+)?(?:adalah\s+|:\s*)?([A-Za-z0-9][A-Za-z0-9\s+,_/-]{2,100}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Technical", "Tech stack", "User's tech stack: {value}.", 0.9, "LOW"),

    # Language preference
    (re.compile(r'(?:bahasa\s+)?(?:pemrograman\s+)?(?:yang\s+saya\s+)?(?:pakai|gunakan|suka)\s+(?:adalah\s+)?([A-Za-z0-9#++\s]{2,40}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Technical", "Programming language", "User uses {value}.", 0.8, "LOW"),

    # Goals
    (re.compile(r'(?:goal|target|tujuan)\s+saya\s+(?:adalah\s+)?([A-Za-z][A-Za-z\s,.]{2,120}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Goals", "User goal", "User's goal: {value}.", 0.8, "LOW"),
]


def rule_based_extract(text: str) -> List[MemoryCandidate]:
    """Extract memory candidates from text using rule-based patterns. Fast, no I/O."""
    if _contains_secret(text):
        return []  # entire message has a secret — skip to be safe

    candidates: List[MemoryCandidate] = []
    seen_titles: set[str] = set()

    for pattern, category, title, content_tpl, confidence, sensitivity in _RULES:
        for m in pattern.finditer(text):
            value = m.group(1).strip().rstrip(".,!?").strip()
            if not value or len(value) < 2:
                continue
            if _contains_secret(value):
                continue
            c = MemoryCandidate(
                category=category,
                title=title,
                content=content_tpl.format(value=value),
                confidence=confidence,
                sensitivity=sensitivity,
                snippet=m.group(0)[:200],
            )
            key = f"{category}:{title}"
            if key not in seen_titles:
                seen_titles.add(key)
                candidates.append(c)

    return candidates


# --------------------------------------------------------------------------- #
# Auto-save vs suggest decision
# --------------------------------------------------------------------------- #

def _auto_save_or_suggest(
    db: Session,
    principal: Principal,
    candidate: MemoryCandidate,
    session_id: Optional[uuid.UUID],
) -> None:
    from app.services import memory_service

    # HIGH sensitivity or low confidence → always suggest, never auto-save.
    needs_approval = candidate.sensitivity in ("MEDIUM", "HIGH") or candidate.confidence < 0.7
    if needs_approval:
        memory_service.create_suggestion(
            db, principal,
            category=candidate.category,
            title=candidate.title,
            content=candidate.content,
            source_session_id=session_id,
            source_snippet=candidate.snippet,
            confidence=candidate.confidence,
            sensitivity=candidate.sensitivity,
        )
        return

    # LOW sensitivity + HIGH confidence → upsert directly (auto-save).
    memory_service.upsert_memory(
        db, principal,
        category=candidate.category,
        title=candidate.title,
        content=candidate.content,
        source="chat_extracted",
        sensitivity=candidate.sensitivity,
        confidence=candidate.confidence,
        source_session_id=session_id,
    )


# --------------------------------------------------------------------------- #
# Background LLM extraction (daemon thread, never blocks response)
# --------------------------------------------------------------------------- #

def _llm_extract_thread(workspace_id_str: str, user_id_str: str, user_msg: str, assistant_msg: str, session_id_str: str) -> None:
    """Runs in a daemon thread. Creates its own DB session. Never raises."""
    from app.core.database import SessionLocal
    from app.core.principal import Principal as _Principal

    db = SessionLocal()
    try:
        principal = _Principal(
            workspace_id=uuid.UUID(workspace_id_str),
            user_id=uuid.UUID(user_id_str),
        )
        session_id = uuid.UUID(session_id_str) if session_id_str else None
        candidates = _llm_extract_candidates(user_msg, assistant_msg, principal, db)
        for c in candidates:
            _auto_save_or_suggest(db, principal, c, session_id)
        db.commit()
    except Exception:  # noqa: BLE001 - background thread must never raise
        pass
    finally:
        db.close()


def _llm_extract_candidates(
    user_msg: str, assistant_msg: str, principal: Principal, db: Session
) -> List[MemoryCandidate]:
    """Use the workspace's default provider to extract memory candidates from a turn.
    Returns empty list if no provider configured or on any error."""
    from app.services import ai_provider_router, ai_settings_service

    if not ai_settings_service.is_memory_auto_learning_enabled(db, principal):
        return []

    plan = ai_provider_router.plan_chat(db, principal, None)
    if not plan.runnable:
        return []

    prompt = (
        "You are a memory extractor. Analyze this conversation turn and identify facts worth remembering "
        "long-term about the user. Return a JSON array of objects with keys: "
        "category (Profile|Preferences|Projects|WorkStyle|Technical|Goals), "
        "title (short, max 50 chars), content (complete sentence), confidence (0.0-1.0), sensitivity (LOW|MEDIUM|HIGH). "
        "Only include high-signal facts. Return [] if nothing important. Do NOT include secrets, passwords, or API keys.\n\n"
        f"User: {user_msg[:800]}\nAssistant: {assistant_msg[:800]}"
    )
    try:
        result = plan.execute([{"role": "user", "content": prompt}])
        if not result.ok or not result.content:
            return []
        import json
        content = result.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        raw = json.loads(content.strip())
        if not isinstance(raw, list):
            return []
        candidates = []
        for item in raw[:10]:
            if not isinstance(item, dict):
                continue
            cat = str(item.get("category", "Profile"))
            title = str(item.get("title", ""))[:200]
            content_str = str(item.get("content", ""))
            conf = float(item.get("confidence", 0.7))
            sens = str(item.get("sensitivity", "LOW"))
            if not title or not content_str or _contains_secret(content_str):
                continue
            candidates.append(MemoryCandidate(
                category=cat, title=title, content=content_str,
                confidence=conf, sensitivity=sens, snippet=user_msg[:200],
            ))
        return candidates
    except Exception:  # noqa: BLE001
        return []


# --------------------------------------------------------------------------- #
# Public entry point (called from chat services after each response)
# --------------------------------------------------------------------------- #

def schedule_extraction(
    db: Session,
    principal: Principal,
    user_msg: str,
    assistant_msg: str,
    session_id: Optional[uuid.UUID],
) -> int:
    """Synchronously run rule-based extraction and optionally start LLM thread.

    Returns the number of memories created/suggested synchronously.
    Never raises — errors are swallowed so they don't affect the main response.
    """
    from app.services import ai_settings_service

    try:
        if not ai_settings_service.is_memory_auto_learning_enabled(db, principal):
            return 0

        candidates = rule_based_extract(user_msg)
        for c in candidates:
            _auto_save_or_suggest(db, principal, c, session_id)
        db.flush()

        # Start LLM background thread if rule-based found nothing but the turn seems informative.
        if not candidates and len(user_msg) > 20:
            t = threading.Thread(
                target=_llm_extract_thread,
                args=(
                    str(principal.workspace_id),
                    str(principal.user_id),
                    user_msg,
                    assistant_msg,
                    str(session_id) if session_id else "",
                ),
                daemon=True,
            )
            t.start()

        return len(candidates)
    except Exception:  # noqa: BLE001
        return 0
```

---

## Task 5: Memory Context Builder

**Files:**
- Create: `backend/app/services/memory_context_builder.py`

- [ ] **Step 5.1: Create the context builder**

```python
# backend/app/services/memory_context_builder.py
"""Builds a compact memory context block to prepend to every AI request.

The block is at most ~800 tokens. It always includes Profile + Preferences.
Projects and section memories are included when relevant.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.domain.ai_memory import AiMemory

# Always include these categories.
_ALWAYS_INCLUDE = ("Profile", "Preferences")

# Include when message seems project-related.
_PROJECT_KEYWORDS = (
    "project", "aplikasi", "app", "sistem", "website", "backend", "frontend",
    "codebase", "fitur", "feature", "deploy", "build", "coding",
)

# Category → section key mappings (matches frontend section_key values).
_SECTION_CATEGORY_MAP = {
    "finance": "Goals",
    "notes": "WorkStyle",
    "tasks": "WorkStyle",
    "calendar": "WorkStyle",
}

MAX_CONTENT_PER_MEMORY = 300
MAX_BLOCK_CHARS = 3000  # ~750 tokens


def _is_project_related(message: str) -> bool:
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in _PROJECT_KEYWORDS)


def _format_block(memories: list[AiMemory]) -> str:
    if not memories:
        return ""
    lines = ["[AI Memory — user context, use when relevant]"]
    by_category: dict[str, list[str]] = {}
    for m in memories:
        by_category.setdefault(m.category, []).append(m.content[:MAX_CONTENT_PER_MEMORY])
    for cat, contents in by_category.items():
        lines.append(f"{cat}:")
        for c in contents:
            lines.append(f"  - {c}")
    lines.append("[End of memory context]")
    return "\n".join(lines)


def build(
    db: Session,
    principal: Principal,
    message: str,
    section_key: Optional[str] = None,
) -> Optional[str]:
    """Return a memory context block string, or None if no relevant memories exist."""
    from app.services import ai_settings_service, memory_service

    if not ai_settings_service.is_memory_auto_learning_enabled(db, principal):
        return None

    selected: list[AiMemory] = []
    seen_ids: set = set()

    def _add(memories: list[AiMemory]) -> None:
        for m in memories:
            if m.id not in seen_ids and m.enabled and m.status == "active":
                seen_ids.add(m.id)
                selected.append(m)

    # Always: Profile + Preferences
    for cat in _ALWAYS_INCLUDE:
        _add(memory_service.get_memories_by_category(db, principal, cat))

    # Conditional: Projects
    if _is_project_related(message):
        _add(memory_service.get_memories_by_category(db, principal, "Projects"))

    # Section-specific
    if section_key and section_key != "general":
        extra_cat = _SECTION_CATEGORY_MAP.get(section_key)
        if extra_cat:
            _add(memory_service.get_memories_by_category(db, principal, extra_cat))
        # Also search memories whose content matches the section key
        _add(memory_service.search_memories(db, principal, section_key, limit=5))

    # Also search memories relevant to the message text (top 3 keyword matches)
    msg_words = [w for w in message.lower().split() if len(w) > 4][:5]
    if msg_words:
        _add(memory_service.search_memories(db, principal, " ".join(msg_words[:3]), limit=5))

    if not selected:
        return None

    # Mark all selected memories as used
    for m in selected:
        memory_service.mark_used(db, principal, m.id)
    db.flush()

    block = _format_block(selected)
    if len(block) > MAX_BLOCK_CHARS:
        block = block[:MAX_BLOCK_CHARS] + "\n[Memory truncated to fit context limit]"
    return block
```

---

## Task 6: Memory Settings in ai_settings_service

**Files:**
- Modify: `backend/app/services/ai_settings_service.py`

- [ ] **Step 6.1: Add memory settings functions**

Read `backend/app/services/ai_settings_service.py`. Find the end of the file and add after the existing `get_chat_settings` / `set_chat_settings` functions:

```python
# Add these constants near the top of ai_settings_service.py:
MEMORY_SETTINGS_PROVIDER_ID = "ai_memory_settings"

MEMORY_DEFAULTS = {
    "auto_learning_enabled": True,
    "require_approval_sensitive": True,
}
```

Add these two functions at the end of the file:

```python
def get_memory_settings(db: Session, principal: Principal) -> dict:
    row = _row(db, principal, MEMORY_SETTINGS_PROVIDER_ID)
    cfg = dict(row.public_config) if row and row.public_config else {}
    return {**MEMORY_DEFAULTS, **{k: v for k, v in cfg.items() if k in MEMORY_DEFAULTS}}


def set_memory_settings(db: Session, principal: Principal, updates: dict) -> dict:
    row = _ensure_row(db, principal, MEMORY_SETTINGS_PROVIDER_ID, "AI Memory Settings")
    valid_keys = set(MEMORY_DEFAULTS.keys())
    cfg = dict(row.public_config or {})
    for k, v in updates.items():
        if k in valid_keys:
            cfg[k] = v
    row.public_config = cfg
    db.commit()
    return {**MEMORY_DEFAULTS, **{k: v for k, v in cfg.items() if k in MEMORY_DEFAULTS}}


def is_memory_auto_learning_enabled(db: Session, principal: Principal) -> bool:
    settings = get_memory_settings(db, principal)
    return bool(settings.get("auto_learning_enabled", True))


def is_memory_require_approval_sensitive(db: Session, principal: Principal) -> bool:
    settings = get_memory_settings(db, principal)
    return bool(settings.get("require_approval_sensitive", True))
```

---

## Task 7: Update ai_orchestrator — Accept extra_context

**Files:**
- Modify: `backend/app/services/ai_orchestrator.py`

- [ ] **Step 7.1: Add extra_context parameter to run_with_tools()**

In `run_with_tools()` signature (line ~80), add `extra_context: Optional[str] = None`:

```python
def run_with_tools(
    db: Session,
    principal: Principal,
    *,
    message: str,
    session_id: Optional[uuid.UUID] = None,
    provider_id: Optional[str] = None,
    extra_context: Optional[str] = None,        # ← ADD THIS
) -> dict:
```

Find the line where `convo` is built (currently `convo: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}, *history, user_turn]`). Replace it with:

```python
    system_content = SYSTEM_PROMPT
    if extra_context:
        system_content = f"{SYSTEM_PROMPT}\n\n{extra_context}"
    convo: List[dict] = [{"role": "system", "content": system_content}, *history, user_turn]
```

Also update the non-tool path (plain chat path) to pass the memory context prepended to the user message:

```python
    if not plan.supports_tool_loop:
        # For non-tool providers: prepend memory context to the user turn.
        if extra_context:
            augmented_turn = {"role": "user", "content": f"{extra_context}\n\nUser: {message}"}
        else:
            augmented_turn = user_turn
        result = plan.execute([*history, augmented_turn])
```

---

## Task 8: Update ai_service.chat() with Memory

**Files:**
- Modify: `backend/app/services/ai_service.py`

- [ ] **Step 8.1: Add section_key parameter and memory integration**

In `chat()` function signature, add `section_key: Optional[str] = "general"`:

```python
def chat(
    db: Session,
    principal: Principal,
    *,
    message: str,
    session_id: Optional[uuid.UUID] = None,
    provider_id: Optional[str] = None,
    section_key: Optional[str] = "general",    # ← ADD
) -> dict:
```

At the top of the function body, add imports and context building (before the `user_message = ChatMessage(...)` line):

```python
    # Build memory context block (inject into system prompt).
    from app.services import memory_context_builder, memory_extraction_service
    extra_context = memory_context_builder.build(db, principal, message, section_key)
```

Change the `ai_orchestrator.run_with_tools` call to pass `extra_context`:

```python
    result = ai_orchestrator.run_with_tools(
        db, principal, message=message, session_id=session.id,
        provider_id=provider_id, extra_context=extra_context,
    )
```

After `db.add(assistant_message)` and `db.commit()`, add extraction:

```python
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    # Trigger hybrid memory extraction (rule-based inline, LLM in background).
    memory_extraction_service.schedule_extraction(
        db, principal, message, result["content"], session.id
    )
    db.commit()  # commit any memories created synchronously
```

---

## Task 9: Update ai_multi_service.multi_chat() with Memory

**Files:**
- Modify: `backend/app/services/ai_multi_service.py`

- [ ] **Step 9.1: Add section_key + memory to multi_chat()**

Add `section_key: Optional[str] = "general"` to `multi_chat()` signature:

```python
def multi_chat(
    db: Session,
    principal: Principal,
    *,
    message: str,
    provider_ids: List[str],
    session_id: Optional[uuid.UUID] = None,
    images: Optional[List[str]] = None,
    thinking_mode: str = "balance",
    section_key: Optional[str] = "general",    # ← ADD
) -> dict:
```

Add at the top of `multi_chat()` body (before session handling):

```python
    from app.services import memory_context_builder, memory_extraction_service
    extra_context = memory_context_builder.build(db, principal, message, section_key)
```

Modify `_messages_for(pid)` inner function to inject context into system message. Replace the function:

```python
    def _messages_for(pid: str) -> list[dict]:
        role_name, role_task = roles[pid]
        mem_prefix = f"{extra_context}\n\n" if extra_context else ""
        if len(ids) == 1:
            system_content = mem_prefix.rstrip("\n") if mem_prefix else None
            if system_content:
                return [{"role": "system", "content": system_content}, base_user]
            return [base_user]
        return [
            {"role": "system", "content": (
                f"{mem_prefix}"
                f"You are the {role_name} agent in a team of {len(ids)} AI agents answering "
                f"the same request. Your job: {role_task} Answer from that perspective — "
                "be specific and concrete, no generic filler, and be honest about uncertainty."
            )},
            base_user,
        ]
```

After the final assistant messages are persisted and `db.commit()` is called, add extraction. Find the `db.commit()` near the end of `multi_chat()` and add after it:

```python
    db.commit()

    # Trigger memory extraction using the user message + first completed agent response.
    first_response = next(
        (r.content for r in responses if r.status == "completed" and r.content),
        "",
    )
    memory_extraction_service.schedule_extraction(
        db, principal, message, first_response or "", session.id
    )
    db.commit()
```

---

## Task 10: Update ai_debate_service.debate_chat() with Memory

**Files:**
- Modify: `backend/app/services/ai_debate_service.py`

- [ ] **Step 10.1: Read the full debate_chat() function**

Read the function signature in `backend/app/services/ai_debate_service.py`. Then:

Add `section_key: Optional[str] = "general"` to `debate_chat()` signature.

Near the top of `debate_chat()` body add:

```python
    from app.services import memory_context_builder, memory_extraction_service
    extra_context = memory_context_builder.build(db, principal, message, section_key)
```

The debate service builds messages differently (per-round). Find where the system message is constructed for each agent's turn and prepend `extra_context` there. Locate the line that builds the opening round system message and add the memory prefix.

In the opening round message builder (typically something like `f"You are debating..."`), change it to:

```python
    mem_prefix = f"{extra_context}\n\n" if extra_context else ""
    # Then use mem_prefix + existing system content
```

After the final synthesis message is committed, add:

```python
    db.commit()
    memory_extraction_service.schedule_extraction(
        db, principal, message, synthesis_content or "", session.id
    )
    db.commit()
```

where `synthesis_content` is the content of the final synthesized message.

---

## Task 11: Update ai_reasoning_service.reasoning_chat() with Memory

**Files:**
- Modify: `backend/app/services/ai_reasoning_service.py`

- [ ] **Step 11.1: Add section_key + memory to reasoning_chat()**

Read `backend/app/services/ai_reasoning_service.py` fully, then:

Add `section_key: Optional[str] = "general"` to `reasoning_chat()` signature.

Add at top of function body:

```python
    from app.services import memory_context_builder, memory_extraction_service
    extra_context = memory_context_builder.build(db, principal, message, section_key)
```

The reasoning service uses `_call()` which takes a prompt string. Modify the analyst prompt to prepend context:

```python
    analyst_prompt = prompts.analyst(message, extra_context)  # pass context to prompt builder
```

In `backend/app/services/reasoning/prompts.py`, add `extra_context` param to the `analyst()` function:

```python
def analyst(user_message: str, extra_context: str | None = None) -> str:
    prefix = f"{extra_context}\n\n" if extra_context else ""
    return f"{prefix}[Analyst role prompt...]{user_message}"
```

After the final answer message is committed, add:

```python
    db.commit()
    final_content = final_answer_row.content if final_answer_row else ""
    memory_extraction_service.schedule_extraction(
        db, principal, message, final_content, session.id
    )
    db.commit()
```

---

## Task 12: Memory Tools in Tool Registry

**Files:**
- Modify: `backend/app/services/ai_tools_registry.py`

- [ ] **Step 12.1: Add memory tool handlers**

After the `_h_current_weather` function block and before `# THE REGISTRY`, add these handlers:

```python
# --------------------------------------------------------------------------- #
# handlers — AI memories (read from registry; write via proposals)
# --------------------------------------------------------------------------- #


def _h_list_memories(db, principal, args) -> dict:
    from app.services import memory_service

    category = args.get("category")
    rows = memory_service.list_memories(db, principal, category=category, enabled_only=True, limit=20)
    return {
        "memories": [
            {"id": str(m.id), "category": m.category, "title": m.title,
             "content": m.content, "source": m.source}
            for m in rows
        ],
        "count": len(rows),
    }


def _h_search_memories(db, principal, args) -> dict:
    from app.services import memory_service

    q = str(args.get("q") or "").strip()
    if not q:
        raise ToolError("Provide a search query 'q'.")
    rows = memory_service.search_memories(db, principal, q, limit=10)
    return {
        "memories": [
            {"id": str(m.id), "category": m.category, "title": m.title, "content": m.content}
            for m in rows
        ],
        "count": len(rows),
    }


def _h_create_memory_tool(db, principal, args) -> dict:
    from app.services import memory_service

    m = memory_service.upsert_memory(
        db, principal,
        category=str(args.get("category") or "Profile"),
        title=str(args.get("title") or ""),
        content=str(args.get("content") or ""),
        source="manual",
        sensitivity="LOW",
        confidence=1.0,
    )
    return {"memory": {"id": str(m.id), "category": m.category, "title": m.title, "content": m.content}}


def _h_update_memory_tool(db, principal, args) -> dict:
    from app.services import memory_service
    import uuid as _uuid

    memory_id = _uuid(args.get("memory_id"), "memory_id")
    m = memory_service.update_memory(
        db, principal, memory_id,
        title=args.get("title"),
        content=args.get("content"),
    )
    return {"memory": {"id": str(m.id), "title": m.title, "content": m.content}}


def _h_delete_memory_tool(db, principal, args) -> dict:
    from app.services import memory_service
    import uuid as _uuid

    memory_id = _uuid(args.get("memory_id"), "memory_id")
    memory_service.delete_memory(db, principal, memory_id)
    return {"deleted": True}
```

Add these ToolSpec entries to the `TOOLS` dict (inside the existing `TOOLS: dict[str, ToolSpec] = {t.name: t for t in (` tuple):

```python
    # --- AI memories ---
    ToolSpec("list_memories", "List the user's AI memories (optionally by category).", "memory", "read", "LOW",
             _schema({"category": _str_prop("Category: Profile|Preferences|Projects|WorkStyle|Technical|Goals")}),
             _h_list_memories),
    ToolSpec("search_memories", "Search AI memories by keyword.", "memory", "read", "LOW",
             _schema({"q": _str_prop("Search query")}, ["q"]),
             _h_search_memories),
    ToolSpec("create_memory", "Create an AI memory for the user.", "memory", "write", "LOW",
             _schema({
                 "category": _str_prop("Profile|Preferences|Projects|WorkStyle|Technical|Goals"),
                 "title": _str_prop("Short descriptor (max 50 chars)"),
                 "content": _str_prop("Complete sentence describing the memory"),
             }, ["category", "title", "content"]),
             _h_create_memory_tool),
    ToolSpec("update_memory", "Update an existing AI memory.", "memory", "write", "LOW",
             _schema({
                 "memory_id": _str_prop("Memory id"),
                 "title": _str_prop("New title"),
                 "content": _str_prop("New content"),
             }, ["memory_id"]),
             _h_update_memory_tool),
    ToolSpec("delete_memory", "Delete an AI memory.", "memory", "write", "MEDIUM",
             _schema({"memory_id": _str_prop("Memory id")}, ["memory_id"]),
             _h_delete_memory_tool),
```

---

## Task 13: Pydantic Schemas for Memory API

**Files:**
- Create: `backend/app/schemas/memory.py`

- [ ] **Step 13.1: Create memory schemas**

```python
# backend/app/schemas/memory.py
"""Pydantic schemas for the AI Memory API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

MemoryCategory = Literal["Profile", "Preferences", "Projects", "WorkStyle", "Technical", "Goals"]
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
```

Also add to `backend/app/schemas/common.py` if `ORMModel` doesn't exist:

```python
# If ORMModel is not already in common.py, check its definition.
# It should be: class ORMModel(BaseModel): model_config = ConfigDict(from_attributes=True)
```

---

## Task 14: Memory API Router

**Files:**
- Create: `backend/app/api/routers/memory.py`

- [ ] **Step 14.1: Create the memory router**

```python
# backend/app/api/routers/memory.py
"""AI Memory endpoints: CRUD, suggestions, settings, and optional Supabase sync."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.memory import (
    MemoryCreate,
    MemoryOut,
    MemorySettingsOut,
    MemorySettingsUpdate,
    MemoryUpdate,
    SuggestionOut,
)
from app.services import ai_settings_service, memory_service

router = APIRouter(prefix="/ai/memory", tags=["ai-memory"])


@router.get("")
def list_memories(
    category: Optional[str] = Query(default=None),
    status: str = Query(default="active"),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    rows = memory_service.list_memories(db, principal, category=category, status=status)
    return success_response([MemoryOut.model_validate(m) for m in rows], "Memories retrieved")


@router.post("")
def create_memory(
    payload: MemoryCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    m = memory_service.create_memory(
        db, principal,
        category=payload.category,
        title=payload.title,
        content=payload.content,
        sensitivity=payload.sensitivity,
        source="manual",
    )
    db.commit()
    db.refresh(m)
    return success_response(MemoryOut.model_validate(m), "Memory created")


@router.get("/search")
def search_memories(
    q: str = Query(min_length=1),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    rows = memory_service.search_memories(db, principal, q)
    return success_response([MemoryOut.model_validate(m) for m in rows], "Search results")


@router.get("/suggestions")
def list_suggestions(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    rows = memory_service.list_suggestions(db, principal)
    return success_response([SuggestionOut.model_validate(s) for s in rows], "Suggestions retrieved")


@router.patch("/{memory_id}")
def update_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    m = memory_service.update_memory(
        db, principal, memory_id,
        title=payload.title, content=payload.content, category=payload.category,
    )
    db.commit()
    db.refresh(m)
    return success_response(MemoryOut.model_validate(m), "Memory updated")


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    memory_service.delete_memory(db, principal, memory_id)
    db.commit()
    return success_response({"id": str(memory_id)}, "Memory deleted")


@router.post("/{memory_id}/enable")
def enable_memory(
    memory_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    m = memory_service.update_memory(db, principal, memory_id, enabled=True)
    db.commit()
    db.refresh(m)
    return success_response(MemoryOut.model_validate(m), "Memory enabled")


@router.post("/{memory_id}/disable")
def disable_memory(
    memory_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    m = memory_service.update_memory(db, principal, memory_id, enabled=False)
    db.commit()
    db.refresh(m)
    return success_response(MemoryOut.model_validate(m), "Memory disabled")


@router.post("/suggestions/{suggestion_id}/approve")
def approve_suggestion(
    suggestion_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    m = memory_service.approve_suggestion(db, principal, suggestion_id)
    db.commit()
    db.refresh(m)
    return success_response(MemoryOut.model_validate(m), "Suggestion approved")


@router.post("/suggestions/{suggestion_id}/reject")
def reject_suggestion(
    suggestion_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    memory_service.reject_suggestion(db, principal, suggestion_id)
    db.commit()
    return success_response({"id": str(suggestion_id)}, "Suggestion rejected")


@router.get("/settings")
def get_memory_settings(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    settings = ai_settings_service.get_memory_settings(db, principal)
    return success_response(MemorySettingsOut(**settings), "Memory settings")


@router.put("/settings")
def update_memory_settings(
    payload: MemorySettingsUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    settings = ai_settings_service.set_memory_settings(db, principal, updates)
    return success_response(MemorySettingsOut(**settings), "Memory settings saved")


@router.post("/clear")
def clear_all_memories(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Delete ALL active memories for this workspace. Irreversible."""
    rows = memory_service.list_memories(db, principal, limit=MAX_MEMORIES_PER_WORKSPACE)
    for m in rows:
        db.delete(m)
    db.commit()
    return success_response({"deleted": len(rows)}, "All memories cleared")


@router.post("/sync/supabase")
def sync_supabase(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    from app.services import supabase_sync_service
    result = supabase_sync_service.sync_all(db, principal)
    return success_response(result, "Supabase sync triggered")
```

Add the missing import at the top:

```python
from app.services.memory_service import MAX_MEMORIES_PER_WORKSPACE
```

---

## Task 15: Register Memory Router in main.py + Update Chat Schemas

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas/ai.py`
- Modify: `backend/app/api/routers/ai.py`

- [ ] **Step 15.1: Register the memory router in main.py**

In `backend/app/main.py`, add to imports:

```python
from app.api.routers import (
    ai,
    auth,
    automations,
    calendar,
    drive,
    finance,
    google,
    health,
    memory,          # ← ADD
    n8n,
    notes,
    settings as settings_router,
    system,
    tasks,
    weather,
)
```

Add to `create_app()`:

```python
    app.include_router(memory.router, prefix=prefix)
```

- [ ] **Step 15.2: Add section_key to all ChatRequest schemas**

In `backend/app/schemas/ai.py`, update `ChatRequest`, `MultiChatRequest`, `DebateChatRequest`, `ReasoningChatRequest` to include `section_key`:

```python
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None
    provider_id: Optional[str] = None
    section_key: Optional[str] = Field(default="general", max_length=50)  # ← ADD


class MultiChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None
    provider_ids: List[str] = Field(min_length=1, max_length=7)
    images: ImageList = Field(default=None, max_length=4)
    thinking_mode: ThinkingMode = "balance"
    section_key: Optional[str] = Field(default="general", max_length=50)  # ← ADD


class DebateChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None
    provider_ids: List[str] = Field(min_length=1, max_length=7)
    rounds: int = Field(default=2, ge=1, le=4)
    images: ImageList = Field(default=None, max_length=4)
    thinking_mode: ThinkingMode = "balance"
    section_key: Optional[str] = Field(default="general", max_length=50)  # ← ADD


class ReasoningChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: Optional[uuid.UUID] = None
    provider_ids: List[str] = Field(min_length=1, max_length=7)
    images: ImageList = Field(default=None, max_length=4)
    thinking_mode: ThinkingMode = "balance"
    section_key: Optional[str] = Field(default="general", max_length=50)  # ← ADD
```

- [ ] **Step 15.3: Pass section_key from AI router to services**

In `backend/app/api/routers/ai.py`, update the `chat()`, `chat_multi()`, `chat_debate()`, and `chat_reason()` endpoint functions to pass `section_key`:

```python
@router.post("/chat")
def chat(payload: ChatRequest, ...) -> dict:
    result = ai_service.chat(
        db, principal,
        message=payload.message,
        session_id=payload.session_id,
        provider_id=payload.provider_id,
        section_key=payload.section_key or "general",   # ← ADD
    )
    ...

@router.post("/chat/multi")
def chat_multi(payload: MultiChatRequest, ...) -> dict:
    result = ai_multi_service.multi_chat(
        db, principal,
        message=payload.message,
        provider_ids=payload.provider_ids,
        session_id=payload.session_id,
        images=payload.images,
        thinking_mode=payload.thinking_mode,
        section_key=payload.section_key or "general",   # ← ADD
    )
    ...

@router.post("/chat/debate")
def chat_debate(payload: DebateChatRequest, ...) -> dict:
    result = ai_debate_service.debate_chat(
        db, principal,
        message=payload.message,
        provider_ids=payload.provider_ids,
        session_id=payload.session_id,
        rounds=payload.rounds,
        images=payload.images,
        thinking_mode=payload.thinking_mode,
        section_key=payload.section_key or "general",   # ← ADD
    )
    ...

@router.post("/chat/reason")
def chat_reason(payload: ReasoningChatRequest, ...) -> dict:
    result = ai_reasoning_service.reasoning_chat(
        db, principal,
        message=payload.message,
        provider_ids=payload.provider_ids,
        session_id=payload.session_id,
        thinking_mode=payload.thinking_mode,
        images=payload.images,
        section_key=payload.section_key or "general",   # ← ADD
    )
    ...
```

---

## Task 16: Supabase Sync Service

**Files:**
- Create: `backend/app/services/supabase_sync_service.py`

- [ ] **Step 16.1: Create the Supabase sync service**

```python
# backend/app/services/supabase_sync_service.py
"""Optional Supabase sync — runs in background, never blocks main flow.

Enabled by configuring SUPABASE_URL and SUPABASE_ANON_KEY via Settings → Integrations.
Sync direction: local PostgreSQL → Supabase (one-way for now).
All sync errors are silently logged — never raised to callers.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.principal import Principal

log = logging.getLogger(__name__)

SUPABASE_PROVIDER_ID = "supabase"


def _get_credentials(db: Session, principal: Principal) -> tuple[Optional[str], Optional[str]]:
    """Return (supabase_url, anon_key) or (None, None) if not configured."""
    from sqlalchemy import select
    from app.domain.integrations import IntegrationConfig
    row = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == principal.workspace_id,
            IntegrationConfig.provider_id == SUPABASE_PROVIDER_ID,
            IntegrationConfig.enabled == True,  # noqa: E712
        )
    )
    if not row:
        return None, None
    url = (row.public_config or {}).get("supabase_url") or ""
    key = None
    if row.secrets:
        from app.core.secrets import decrypt_secret
        raw = row.secrets.get("anon_key")
        if raw:
            try:
                key = decrypt_secret(raw)
            except Exception:
                pass
    return url or None, key or None


def is_enabled(db: Session, principal: Principal) -> bool:
    url, key = _get_credentials(db, principal)
    return bool(url and key)


def sync_all(db: Session, principal: Principal) -> dict:
    """Trigger a background sync and return immediately."""
    import threading
    url, key = _get_credentials(db, principal)
    if not url or not key:
        return {"status": "not_configured", "message": "Configure Supabase URL and anon key in Settings → Integrations."}

    workspace_id = str(principal.workspace_id)
    t = threading.Thread(
        target=_sync_thread, args=(url, key, workspace_id), daemon=True
    )
    t.start()
    return {"status": "syncing", "message": "Background sync started."}


def _sync_thread(url: str, key: str, workspace_id: str) -> None:
    """Runs in a daemon thread. Creates its own DB session. Never raises."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        _do_sync(db, url, key, workspace_id)
    except Exception as exc:
        log.debug("Supabase sync error: %s", exc)
    finally:
        db.close()


def _do_sync(db: Session, url: str, key: str, workspace_id: str) -> None:
    """Attempt to sync AI tables to Supabase using the REST API (no SDK required)."""
    import json
    import uuid as _uuid
    import urllib.request

    ws = _uuid.UUID(workspace_id)

    def _upsert(table: str, rows: list[dict]) -> None:
        if not rows:
            return
        data = json.dumps(rows).encode()
        req = urllib.request.Request(
            f"{url.rstrip('/')}/rest/v1/{table}",
            data=data,
            headers={
                "Content-Type": "application/json",
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Prefer": "resolution=merge-duplicates",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass

    def _serialize(row) -> dict:
        result = {}
        for col in row.__table__.columns:
            val = getattr(row, col.key, None)
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            elif hasattr(val, "__str__") and not isinstance(val, (str, int, float, bool, type(None))):
                val = str(val)
            result[col.key] = val
        return result

    # Sync ai_memories
    from sqlalchemy import select
    from app.domain.ai_memory import AiMemory, AiMemorySuggestion
    from app.domain.ai import ChatSession, ChatMessage, AiToolProposal, AiMultiAgentRun

    memories = list(db.scalars(select(AiMemory).where(AiMemory.workspace_id == ws)).all())
    _upsert("ai_memories", [_serialize(m) for m in memories])

    suggestions = list(db.scalars(select(AiMemorySuggestion).where(AiMemorySuggestion.workspace_id == ws)).all())
    _upsert("ai_memory_suggestions", [_serialize(s) for s in suggestions])

    sessions = list(db.scalars(select(ChatSession).where(ChatSession.workspace_id == ws)).all())
    _upsert("chat_sessions", [_serialize(s) for s in sessions])

    messages = list(db.scalars(select(ChatMessage).where(ChatMessage.workspace_id == ws)).all())
    _upsert("chat_messages", [_serialize(m) for m in messages])

    proposals = list(db.scalars(select(AiToolProposal).where(AiToolProposal.workspace_id == ws)).all())
    _upsert("ai_tool_proposals", [_serialize(p) for p in proposals])

    runs = list(db.scalars(select(AiMultiAgentRun).where(AiMultiAgentRun.workspace_id == ws)).all())
    _upsert("ai_multi_agent_runs", [_serialize(r) for r in runs])
```

---

## Task 17: Frontend Types + API Client

**Files:**
- Modify: `frontend/types/index.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 17.1: Add memory types to index.ts**

Append to end of `frontend/types/index.ts`:

```typescript
// --- AI Memory ---
export type MemoryCategory = "Profile" | "Preferences" | "Projects" | "WorkStyle" | "Technical" | "Goals";
export type MemorySensitivity = "LOW" | "MEDIUM" | "HIGH";
export type MemorySource = "chat_extracted" | "manual" | "llm_extracted";

export interface AiMemory {
  id: string;
  category: MemoryCategory;
  title: string;
  content: string;
  source: MemorySource;
  status: string;
  sensitivity: MemorySensitivity;
  enabled: boolean;
  confidence: number;
  relevance_score: number;
  last_used_at: string | null;
  source_session_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemorySuggestion {
  id: string;
  memory_id: string | null;
  category: MemoryCategory;
  title: string;
  content: string;
  source_session_id: string | null;
  source_snippet: string | null;
  confidence: number;
  sensitivity: MemorySensitivity;
  extraction_method: "rule_based" | "llm";
  status: string;
  created_at: string;
}

export interface MemorySettings {
  auto_learning_enabled: boolean;
  require_approval_sensitive: boolean;
}
```

- [ ] **Step 17.2: Add memoryApi to lib/api.ts**

After the `aiApi` object (after the closing `};`), add:

```typescript
// --- AI Memory ---
export const memoryApi = {
  list: (category?: string, status = "active") =>
    request<AiMemory[]>(`/ai/memory${category ? `?category=${category}` : ""}${status !== "active" ? `${category ? "&" : "?"}status=${status}` : ""}`),
  create: (payload: { category: string; title: string; content: string; sensitivity?: string }) =>
    request<AiMemory>("/ai/memory", { method: "POST", body: json(payload) }),
  search: (q: string) =>
    request<AiMemory[]>(`/ai/memory/search?q=${encodeURIComponent(q)}`),
  update: (id: string, payload: { title?: string; content?: string; category?: string }) =>
    request<AiMemory>(`/ai/memory/${id}`, { method: "PATCH", body: json(payload) }),
  remove: (id: string) =>
    request<{ id: string }>(`/ai/memory/${id}`, { method: "DELETE" }),
  enable: (id: string) =>
    request<AiMemory>(`/ai/memory/${id}/enable`, { method: "POST" }),
  disable: (id: string) =>
    request<AiMemory>(`/ai/memory/${id}/disable`, { method: "POST" }),
  listSuggestions: () =>
    request<MemorySuggestion[]>("/ai/memory/suggestions"),
  approveSuggestion: (id: string) =>
    request<AiMemory>(`/ai/memory/suggestions/${id}/approve`, { method: "POST" }),
  rejectSuggestion: (id: string) =>
    request<{ id: string }>(`/ai/memory/suggestions/${id}/reject`, { method: "POST" }),
  getSettings: () =>
    request<MemorySettings>("/ai/memory/settings"),
  updateSettings: (payload: Partial<MemorySettings>) =>
    request<MemorySettings>("/ai/memory/settings", { method: "PUT", body: json(payload) }),
  clearAll: () =>
    request<{ deleted: number }>("/ai/memory/clear", { method: "POST" }),
  syncSupabase: () =>
    request<{ status: string; message: string }>("/ai/memory/sync/supabase", { method: "POST" }),
};
```

Add the import for the new types at the top of lib/api.ts:

```typescript
import type {
  // ... existing imports ...
  AiMemory,
  MemorySuggestion,
  MemorySettings,
} from "@/types";
```

- [ ] **Step 17.3: Update aiApi chat methods to accept section_key**

Update the four chat methods in `aiApi` to accept and forward `section_key`:

```typescript
  chat: (message: string, sessionId?: string, providerId?: string, sectionKey = "general") =>
    request<ChatResponse>("/ai/chat", {
      method: "POST",
      body: json({ message, session_id: sessionId || null, provider_id: providerId || null, section_key: sectionKey }),
    }),
  multiChat: (message: string, providerIds: string[], sessionId?: string, images?: string[], thinkingMode = "balance", sectionKey = "general") =>
    request<MultiChatResponse>("/ai/chat/multi", {
      method: "POST",
      body: json({ message, provider_ids: providerIds, session_id: sessionId || null, images: images?.length ? images : null, thinking_mode: thinkingMode, section_key: sectionKey }),
    }),
  debateChat: (message: string, providerIds: string[], sessionId?: string, rounds = 2, images?: string[], thinkingMode = "balance", sectionKey = "general") =>
    request<MultiChatResponse>("/ai/chat/debate", {
      method: "POST",
      body: json({ message, provider_ids: providerIds, session_id: sessionId || null, rounds, images: images?.length ? images : null, thinking_mode: thinkingMode, section_key: sectionKey }),
    }),
  reasonChat: (message: string, providerIds: string[], sessionId?: string, thinkingMode = "balance", images?: string[], sectionKey = "general") =>
    request<MultiChatResponse>("/ai/chat/reason", {
      method: "POST",
      body: json({ message, provider_ids: providerIds, session_id: sessionId || null, thinking_mode: thinkingMode, images: images?.length ? images : null, section_key: sectionKey }),
    }),
```

---

## Task 18: Memory Management Page (Frontend)

**Files:**
- Create: `frontend/app/dashboard/ai/memory/page.tsx`

- [ ] **Step 18.1: Create the memory management page**

```typescript
// frontend/app/dashboard/ai/memory/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft, Brain, Check, ChevronDown, Plus, Search, Trash2, X, Zap,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Toggle } from "@/components/ui/Toggle";
import { memoryApi, ApiException } from "@/lib/api";
import { cn } from "@/lib/format";
import type { AiMemory, MemorySuggestion, MemorySettings, MemoryCategory } from "@/types";

const CATEGORIES: MemoryCategory[] = ["Profile", "Preferences", "Projects", "WorkStyle", "Technical", "Goals"];

const CATEGORY_COLORS: Record<MemoryCategory, string> = {
  Profile: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  Preferences: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  Projects: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  WorkStyle: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  Technical: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  Goals: "bg-rose-500/10 text-rose-400 border-rose-500/20",
};

const SOURCE_LABELS: Record<string, string> = {
  chat_extracted: "Auto-learned",
  manual: "Manual",
  llm_extracted: "AI-extracted",
};

type Tab = "all" | "auto" | "manual" | "pending";

export default function MemoryPage() {
  const [memories, setMemories] = useState<AiMemory[]>([]);
  const [suggestions, setSuggestions] = useState<MemorySuggestion[]>([]);
  const [settings, setSettings] = useState<MemorySettings | null>(null);
  const [tab, setTab] = useState<Tab>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [searchQ, setSearchQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [newMemory, setNewMemory] = useState({ category: "Profile" as MemoryCategory, title: "", content: "" });

  const load = async () => {
    setLoading(true);
    try {
      const [mems, suggs, s] = await Promise.all([
        memoryApi.list(),
        memoryApi.listSuggestions(),
        memoryApi.getSettings(),
      ]);
      setMemories(mems);
      setSuggestions(suggs);
      setSettings(s);
    } catch (e) {
      setError(e instanceof ApiException ? e.message : "Failed to load memories.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const handleSearch = async () => {
    if (!searchQ.trim()) { void load(); return; }
    try {
      const results = await memoryApi.search(searchQ);
      setMemories(results);
    } catch { /* ignore */ }
  };

  const handleToggleEnabled = async (m: AiMemory) => {
    try {
      const updated = m.enabled ? await memoryApi.disable(m.id) : await memoryApi.enable(m.id);
      setMemories((prev) => prev.map((x) => x.id === m.id ? updated : x));
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Delete this memory?")) return;
    try {
      await memoryApi.remove(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch { /* ignore */ }
  };

  const handleSaveEdit = async (id: string) => {
    try {
      const updated = await memoryApi.update(id, { content: editContent });
      setMemories((prev) => prev.map((m) => m.id === id ? updated : m));
      setEditingId(null);
    } catch { /* ignore */ }
  };

  const handleApproveSuggestion = async (id: string) => {
    try {
      const m = await memoryApi.approveSuggestion(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
      setMemories((prev) => [m, ...prev]);
    } catch { /* ignore */ }
  };

  const handleRejectSuggestion = async (id: string) => {
    try {
      await memoryApi.rejectSuggestion(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
    } catch { /* ignore */ }
  };

  const handleAddMemory = async () => {
    if (!newMemory.title.trim() || !newMemory.content.trim()) return;
    try {
      const m = await memoryApi.create(newMemory);
      setMemories((prev) => [m, ...prev]);
      setNewMemory({ category: "Profile", title: "", content: "" });
      setShowAddForm(false);
    } catch { /* ignore */ }
  };

  const handleUpdateSettings = async (patch: Partial<MemorySettings>) => {
    if (!settings) return;
    const next = { ...settings, ...patch };
    setSettings(next);
    try {
      const saved = await memoryApi.updateSettings(patch);
      setSettings(saved);
    } catch { setSettings(settings); }
  };

  const handleClearAll = async () => {
    if (!window.confirm("Delete ALL memories? This cannot be undone.")) return;
    try {
      await memoryApi.clearAll();
      setMemories([]);
    } catch { /* ignore */ }
  };

  const filtered = memories.filter((m) => {
    if (tab === "auto" && m.source === "manual") return false;
    if (tab === "manual" && m.source !== "manual") return false;
    if (categoryFilter !== "all" && m.category !== categoryFilter) return false;
    return true;
  });

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Link href="/dashboard/ai" className="rounded-md p-1.5 text-content-muted hover:bg-surface-raised hover:text-content">
            <ArrowLeft size={17} />
          </Link>
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Brain size={18} />
          </span>
          <div>
            <h1 className="text-lg font-semibold text-content">AI Memory</h1>
            <p className="text-[12px] text-content-muted">
              {memories.length} memories · {suggestions.length} pending
            </p>
          </div>
          <div className="ml-auto flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => setShowAddForm((v) => !v)}>
              <Plus size={14} className="mr-1" /> Add Memory
            </Button>
          </div>
        </div>

        {/* Settings Bar */}
        {settings && (
          <div className="flex flex-wrap items-center gap-4 rounded-xl border border-border bg-surface/50 px-4 py-3">
            <span className="text-[12px] font-medium text-content-muted">Settings</span>
            <label className="flex items-center gap-2 text-[12px] text-content-muted">
              <Toggle
                checked={settings.auto_learning_enabled}
                onChange={(v) => void handleUpdateSettings({ auto_learning_enabled: v })}
                label="Auto-learning"
              />
              Auto-learning
            </label>
            <label className="flex items-center gap-2 text-[12px] text-content-muted">
              <Toggle
                checked={settings.require_approval_sensitive}
                onChange={(v) => void handleUpdateSettings({ require_approval_sensitive: v })}
                label="Require approval"
              />
              Require approval for sensitive
            </label>
            <button
              onClick={handleClearAll}
              className="ml-auto text-[11.5px] text-danger hover:underline"
            >
              Clear all memories
            </button>
          </div>
        )}

        {/* Add form */}
        {showAddForm && (
          <div className="rounded-xl border border-border bg-surface/50 p-4 space-y-3">
            <p className="text-[13px] font-medium text-content">Add Memory</p>
            <div className="flex gap-2">
              <select
                value={newMemory.category}
                onChange={(e) => setNewMemory((p) => ({ ...p, category: e.target.value as MemoryCategory }))}
                className="rounded-md border border-border bg-surface-input px-2 py-1.5 text-[12px] text-content"
              >
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <Input
                value={newMemory.title}
                onChange={(e) => setNewMemory((p) => ({ ...p, title: e.target.value }))}
                placeholder="Title (e.g. User name)"
                className="flex-1 text-[12px]"
              />
            </div>
            <textarea
              value={newMemory.content}
              onChange={(e) => setNewMemory((p) => ({ ...p, content: e.target.value }))}
              placeholder="Memory content (e.g. User's name is Joshua.)"
              rows={2}
              className="w-full rounded-md border border-border bg-surface-input px-3 py-2 text-[12px] text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none"
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleAddMemory}>Save</Button>
              <Button size="sm" variant="secondary" onClick={() => setShowAddForm(false)}>Cancel</Button>
            </div>
          </div>
        )}

        {/* Pending Suggestions */}
        {suggestions.length > 0 && (
          <div className="space-y-2">
            <p className="flex items-center gap-1.5 text-[12px] font-medium text-content-muted">
              <Zap size={13} className="text-warning" />
              {suggestions.length} pending suggestion{suggestions.length > 1 ? "s" : ""}
            </p>
            {suggestions.map((s) => (
              <div
                key={s.id}
                className="flex items-start gap-3 rounded-xl border border-warning/20 bg-warning/5 p-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className={cn("rounded-md border px-1.5 py-0.5 text-[10px] font-medium", CATEGORY_COLORS[s.category as MemoryCategory] ?? "")}>
                      {s.category}
                    </span>
                    <span className="text-[12px] font-medium text-content">{s.title}</span>
                    <Badge tone={s.sensitivity === "LOW" ? "success" : "warning"} className="text-[10px]">
                      {s.sensitivity}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-[12px] text-content-muted">{s.content}</p>
                  {s.source_snippet && (
                    <p className="mt-0.5 text-[10.5px] text-content-subtle italic">
                      From: &ldquo;{s.source_snippet}&rdquo;
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 gap-1.5">
                  <button
                    onClick={() => void handleApproveSuggestion(s.id)}
                    className="flex items-center gap-1 rounded-md border border-success/30 bg-success/10 px-2 py-1 text-[11px] text-success hover:bg-success/20"
                  >
                    <Check size={11} /> Save
                  </button>
                  <button
                    onClick={() => void handleRejectSuggestion(s.id)}
                    className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-content-muted hover:bg-surface-raised"
                  >
                    <X size={11} /> Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Tab + Filter */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-border bg-surface-input p-0.5 text-[12px]">
            {(["all", "auto", "manual", "pending"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  "rounded-md px-3 py-1 capitalize transition-colors",
                  tab === t ? "bg-surface-high text-content" : "text-content-muted hover:text-content",
                )}
              >
                {t === "all" ? `All (${memories.length})` : t === "pending" ? `Pending (${suggestions.length})` : t === "auto" ? "Auto-learned" : "Manual"}
              </button>
            ))}
          </div>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded-md border border-border bg-surface-input px-2 py-1 text-[12px] text-content-muted"
          >
            <option value="all">All categories</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <div className="flex min-w-0 flex-1 items-center gap-1.5 rounded-md border border-border bg-surface-input px-2">
            <Search size={13} className="shrink-0 text-content-subtle" />
            <input
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleSearch()}
              placeholder="Search memories…"
              className="min-w-0 flex-1 bg-transparent py-1 text-[12px] text-content placeholder:text-content-subtle focus:outline-none"
            />
          </div>
        </div>

        {/* Memory List */}
        {error && <p className="text-[12px] text-danger">{error}</p>}
        {loading ? (
          <p className="text-[12px] text-content-muted">Loading memories…</p>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center py-12 text-center">
            <Brain size={32} className="mb-3 text-content-subtle" />
            <p className="text-[13px] text-content-muted">No memories yet.</p>
            <p className="mt-1 text-[12px] text-content-subtle">
              {settings?.auto_learning_enabled
                ? "Chat with AI and it will auto-learn important facts about you."
                : "Auto-learning is off. Enable it in settings, or add memories manually."}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((m) => (
              <div
                key={m.id}
                className={cn(
                  "rounded-xl border p-3 transition-colors",
                  m.enabled ? "border-border bg-surface/50" : "border-border/50 bg-surface/20 opacity-60",
                )}
              >
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className={cn("rounded-md border px-1.5 py-0.5 text-[10px] font-medium", CATEGORY_COLORS[m.category as MemoryCategory] ?? "")}>
                        {m.category}
                      </span>
                      <span className="text-[12.5px] font-medium text-content">{m.title}</span>
                      <Badge tone="neutral" className="text-[10px]">
                        {SOURCE_LABELS[m.source] ?? m.source}
                      </Badge>
                      {m.sensitivity !== "LOW" && (
                        <Badge tone="warning" className="text-[10px]">{m.sensitivity}</Badge>
                      )}
                    </div>
                    {editingId === m.id ? (
                      <div className="mt-1.5 space-y-1.5">
                        <textarea
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          rows={2}
                          className="w-full rounded-md border border-border bg-surface-input px-2.5 py-1.5 text-[12px] text-content focus:border-primary/70 focus:outline-none"
                        />
                        <div className="flex gap-1.5">
                          <Button size="sm" onClick={() => void handleSaveEdit(m.id)}>Save</Button>
                          <Button size="sm" variant="secondary" onClick={() => setEditingId(null)}>Cancel</Button>
                        </div>
                      </div>
                    ) : (
                      <p
                        className="mt-0.5 cursor-text text-[12px] text-content-muted hover:text-content"
                        onClick={() => { setEditingId(m.id); setEditContent(m.content); }}
                        title="Click to edit"
                      >
                        {m.content}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Toggle
                      checked={m.enabled}
                      onChange={() => void handleToggleEnabled(m)}
                      label={m.enabled ? "Enabled" : "Disabled"}
                    />
                    <button
                      onClick={() => void handleDelete(m.id)}
                      className="rounded-md p-1 text-content-subtle hover:text-danger"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
```

---

## Task 19: In-Chat Memory Indicator + Update AI Chat Page

**Files:**
- Create: `frontend/components/ai/MemoryIndicator.tsx`
- Modify: `frontend/app/dashboard/ai/page.tsx`
- Modify: `frontend/components/layout/nav.ts`

- [ ] **Step 19.1: Create MemoryIndicator component**

```typescript
// frontend/components/ai/MemoryIndicator.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Brain, Clock } from "lucide-react";
import { memoryApi } from "@/lib/api";
import { cn } from "@/lib/format";

type IndicatorState = "idle" | "updated" | "pending";

interface MemoryIndicatorProps {
  /** Bump this counter after each AI response to trigger a refresh. */
  refreshKey: number;
  className?: string;
}

export function MemoryIndicator({ refreshKey, className }: MemoryIndicatorProps) {
  const [state, setState] = useState<IndicatorState>("idle");
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    if (refreshKey === 0) return;
    // Show "updated" flash briefly, then check for pending suggestions.
    setState("updated");
    const timer = setTimeout(() => {
      memoryApi.listSuggestions()
        .then((s) => {
          setPendingCount(s.length);
          setState(s.length > 0 ? "pending" : "idle");
        })
        .catch(() => setState("idle"));
    }, 1500);
    return () => clearTimeout(timer);
  }, [refreshKey]);

  if (state === "idle" && pendingCount === 0) return null;

  return (
    <Link
      href="/dashboard/ai/memory"
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
        state === "updated"
          ? "border-success/30 bg-success/10 text-success"
          : "border-warning/30 bg-warning/10 text-warning",
        className,
      )}
    >
      {state === "updated" ? (
        <><Brain size={11} /> Memory updated</>
      ) : (
        <><Clock size={11} /> {pendingCount} memory pending</>
      )}
    </Link>
  );
}
```

- [ ] **Step 19.2: Update AI Chat page**

In `frontend/app/dashboard/ai/page.tsx`:

1. Add import for `MemoryIndicator`:
```typescript
import { MemoryIndicator } from "@/components/ai/MemoryIndicator";
```

2. Add `memoryRefreshKey` state after `proposalRefresh`:
```typescript
const [memoryRefreshKey, setMemoryRefreshKey] = useState(0);
```

3. In the `send()` function's `finally` block, add:
```typescript
    } finally {
      setSending(false);
      setPendingUser(null);
      setPendingImages([]);
      setProposalRefresh((n) => n + 1);
      setMemoryRefreshKey((n) => n + 1);   // ← ADD
    }
```

4. In the chat call, pass the `section` as `sectionKey`:
```typescript
      const run = mode === "debate"
        ? await aiApi.debateChat(sendText, selected, activeId ?? undefined, rounds, imgs, thinking, section)
        : mode === "reason"
          ? await aiApi.reasonChat(sendText, selected, activeId ?? undefined, thinking, imgs, section)
          : await aiApi.multiChat(sendText, selected, activeId ?? undefined, imgs, thinking, section);
```

5. Add `MemoryIndicator` in the chat header, after `SectionMemoryBar`:
```typescript
              <MemoryIndicator refreshKey={memoryRefreshKey} />
```

- [ ] **Step 19.3: Add AI Memory to nav**

In `frontend/components/layout/nav.ts`, add to `MODULE_NAV`:

```typescript
  { href: "/dashboard/ai/memory", label: "AI Memory", icon: Brain, badge: "NEW" },
```

Add `Brain` to the lucide-react import.

---

## Task 20: Verify End-to-End — Acceptance Tests

> Executed sandbox-adapted (no Docker/Postgres): see
> `2026-06-12-ai-memory-system-verification.md` for what was verified live over
> HTTP, what was adapted, and which provider-dependent steps remain manual.

- [x] **Step 20.1: Start the backend and run the migration**

```bash
cd /mnt/storage/VSCode/Repo/AllHaven-Application
docker-compose up -d postgres
cd backend
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- [x] **Step 20.2: Acceptance Test A — Name memory** (memory creation verified live; AI-recall step needs a real provider — manual)

1. Open AI Chat at `http://localhost:3000/dashboard/ai`
2. Send: `"nama saya Joshua"`
3. Wait for response
4. Check `http://localhost:3000/dashboard/ai/memory` — should show a "Profile / User name" memory
5. Start a new chat session
6. Send: `"siapa nama saya?"`
7. AI should respond mentioning "Joshua"

Expected memory in DB:
```sql
SELECT category, title, content FROM ai_memories WHERE workspace_id = '...';
-- Profile | User name | User's name is Joshua.
```

- [x] **Step 20.3: Acceptance Test B — Preference memory** (memory creation verified live; "sharper responses" needs a real provider — manual)

1. Send: `"saya suka jawaban singkat, tajam, dan tidak fake"`
2. Check memory page — should show "Preferences / Response style preference"
3. Ask a question — AI responses should become sharper

- [x] **Step 20.4: Acceptance Test C — Secret detection**

1. Send: `"API key saya adalah sk-abc123def456ghi789jkl"`
2. Check memory page — NO memory should be created
3. Check suggestions — no suggestion with API key content

- [ ] **Step 20.5: Acceptance Test D — Finance tool (existing)**

1. Send: `"ringkas pengeluaran bulan ini"`
2. AI should call `finance_monthly_summary` tool and return real data

- [ ] **Step 20.6: Acceptance Test E — Calendar tool (existing)**

1. Add a calendar event via the Calendar page
2. Send: `"apa jadwal saya hari ini?"`
3. AI should call `list_events` tool and return the event

- [x] **Step 20.7: Acceptance Test F — Disable memory**

1. Go to AI Memory page
2. Disable auto-learning
3. Chat and say your name
4. Check memory page — nothing new should be added

---

## Self-Review Checklist

- [x] All 3 DB tables defined in domain model + migration
- [x] Memory service has full CRUD + deduplication + upsert
- [x] Extraction: rule-based patterns cover name, project, preferences, role, tech, goals
- [x] Secret detection runs BEFORE any save — blocks API keys, JWTs, Bearer tokens
- [x] LLM background thread creates its own DB session (never shares with request session)
- [x] Context builder always includes Profile + Preferences, conditionally adds Projects + section
- [x] All 4 chat modes (single, multi, debate, reason) get memory context injection + extraction
- [x] Memory tools in Tool Registry: 2 reads (list, search) + 3 writes via approval (create, update, delete)
- [x] Memory API router covers all CRUD + suggestions + settings + Supabase sync
- [x] Frontend memory page: list, search, edit, delete, enable/disable, approve/reject suggestions, settings
- [x] In-chat indicator: shows "Memory updated" flash → checks for pending suggestions
- [x] `section_key` flows from frontend → schema → service → context builder
- [x] Supabase sync: daemon thread, never blocks, uses urllib (no SDK dependency)
- [x] All write operations require explicit `db.commit()` after flush
- [x] Memory page accessible via nav + link from AI Chat page
