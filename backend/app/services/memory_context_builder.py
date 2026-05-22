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


def as_prefix(extra_context: Optional[str]) -> str:
    """Format a context block as a prompt prefix ('' when absent)."""
    return f"{extra_context}\n\n" if extra_context else ""


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
