# backend/app/services/memory_context_builder.py
"""Builds a compact memory context block to prepend to every AI request.

The block is at most ~800 tokens. It always includes durable user profile,
preferences, and writing style, then ranks section/message-relevant memories.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.domain.ai_memory import AiMemory

# Always include these categories.
_ALWAYS_INCLUDE = ("Profile", "Preferences", "Writing style")

# Include when message seems project-related.
_PROJECT_KEYWORDS = (
    "project", "aplikasi", "app", "sistem", "website", "backend", "frontend",
    "codebase", "fitur", "feature", "deploy", "build", "coding",
)

# Category → section key mappings (matches frontend section_key values).
_SECTION_CATEGORY_MAP = {
    "finance": ("Finance context", "Goals"),
    "notes": ("Work context", "Writing style"),
    "tasks": ("Tasks context", "Work context"),
    "calendar": ("Work context",),
    "routines": ("Work context",),
    "drive": ("Work context",),
    "files": ("Work context",),
    "ai_knowledge": ("Projects",),
}

MAX_CONTENT_PER_MEMORY = 300
MAX_BLOCK_CHARS = 3000  # ~750 tokens
MAX_SELECTED_MEMORIES = 12

_STOPWORDS = {
    "yang", "dan", "atau", "untuk", "dengan", "saya", "kamu", "anda", "dari",
    "ini", "itu", "the", "and", "with", "from", "about", "what", "when",
    "where", "tolong", "minta", "bisa", "mau",
}


def as_prefix(extra_context: Optional[str]) -> str:
    """Format a context block as a prompt prefix ('' when absent)."""
    return f"{extra_context}\n\n" if extra_context else ""


def _is_project_related(message: str) -> bool:
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in _PROJECT_KEYWORDS)


def _tokens(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-zA-Z0-9_]{3,}", (text or "").lower())
        if t not in _STOPWORDS
    }


def _ranked_relevant(memories: list[AiMemory], message: str, section_key: Optional[str]) -> list[AiMemory]:
    msg_tokens = _tokens(message)
    section_cats = set(_SECTION_CATEGORY_MAP.get(section_key or "", ()))

    def _score(m: AiMemory) -> float:
        text_tokens = _tokens(f"{m.title} {m.content} {m.category}")
        overlap = len(msg_tokens & text_tokens)
        score = float(m.relevance_score or 0)
        score += overlap * 0.25
        if m.category in _ALWAYS_INCLUDE:
            score += 1.25
        if m.category in section_cats:
            score += 0.9
        if section_key and section_key.lower() in (m.content or "").lower():
            score += 0.5
        if m.last_used_at:
            score += 0.15
        return score

    return sorted(memories, key=_score, reverse=True)


def _format_block(memories: list[AiMemory]) -> str:
    if not memories:
        return ""
    lines = ["[AI Memory - user context, use when relevant]"]
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
            if m.id not in seen_ids and m.enabled and m.status == "active" and not getattr(m, "is_deleted", False):
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
        extra_cats = _SECTION_CATEGORY_MAP.get(section_key) or ()
        for extra_cat in extra_cats:
            _add(memory_service.get_memories_by_category(db, principal, extra_cat))
        # Also search memories whose content matches the section key
        _add(memory_service.search_memories(db, principal, section_key, limit=5))

    # Rank across the user's enabled memory set. This catches partial keyword
    # matches better than a single SQL "contains whole phrase" search.
    all_active = memory_service.list_memories(db, principal, enabled_only=True, limit=120)
    for m in _ranked_relevant(all_active, message, section_key):
        _add([m])
        if len(selected) >= MAX_SELECTED_MEMORIES:
            break

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
