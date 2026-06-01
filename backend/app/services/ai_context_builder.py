"""Context packet builder for AI chat requests.

This composes durable context without giving the model raw database access:
recent chat snippets, conversation summaries, relevant memories, section hints,
and AI Knowledge chunks retrieved through backend services.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.domain.ai import ChatMessage
from app.domain.ai_memory import AiConversationSummary
from app.services.thinking import normalize_thinking


@dataclass(frozen=True)
class ContextBudget:
    recent_messages: int
    knowledge_chunks: int
    include_old_search: bool
    label: str
    instruction: str


_BUDGETS = {
    "fast": ContextBudget(8, 1, False, "Fast", "Answer briefly and directly. Use tools only when clearly necessary."),
    "balance": ContextBudget(20, 3, False, "Balance", "Use relevant memory and tools; keep the answer practical, direct, and specific."),
    "thinking": ContextBudget(35, 4, False, "Thinking", "Be careful, check assumptions, and use tools when they reduce uncertainty. Keep the final answer concise."),
    "deep": ContextBudget(55, 6, True, "Deep", "Use deeper context and retrieve knowledge when relevant, but still start with the answer and avoid filler."),
}

_SECTION_HINTS = {
    "general": "General workspace context. Use broad memory and project context.",
    "tasks": "Tasks section. Prioritize task tools; save/add/apply task requests must become pending task actions.",
    "notes": "Notes section. Prioritize notes tools; apply/save note requests must become pending note actions.",
    "finance": "Finance section. Prioritize finance tools and read real finance data before answering spending questions.",
    "calendar": "Calendar section. Prioritize calendar tools for schedule/event requests.",
    "files": "Files section. Use Drive metadata/search tools; do not claim file contents unless a supported summarizer/knowledge result exists.",
    "drive": "Files section. Use Drive metadata/search tools; do not claim file contents unless a supported summarizer/knowledge result exists.",
    "ai_knowledge": "AI Knowledge section. Prioritize knowledge search/retrieval and cite retrieved document context when used.",
}

_KNOWLEDGE_TRIGGERS = (
    "knowledge", "dokumen", "document", "file knowledge", "berdasarkan knowledge",
    "berdasarkan dokumen", "referensi", "uploaded", "unggah", "pdf", "docx",
)


def _budget(mode: str | None) -> ContextBudget:
    return _BUDGETS[normalize_thinking(mode)]


def _recent_messages(db: Session, principal: Principal, session_id: Optional[uuid.UUID], limit: int) -> list[ChatMessage]:
    if not session_id:
        return []
    rows = list(db.scalars(
        select(ChatMessage)
        .where(ChatMessage.workspace_id == principal.workspace_id, ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    ).all())
    rows.reverse()
    return rows


def _summary(db: Session, principal: Principal, session_id: Optional[uuid.UUID]) -> str | None:
    if not session_id:
        return None
    row = db.scalar(
        select(AiConversationSummary).where(
            AiConversationSummary.workspace_id == principal.workspace_id,
            AiConversationSummary.session_id == session_id,
        )
    )
    return row.summary if row else None


_LANGUAGE_INSTRUCTIONS = {
    "id": "Answer in natural Bahasa Indonesia unless the user explicitly asks for another language.",
    "en": "Answer in concise English unless the user explicitly asks for another language.",
    "zh-Hant": "請使用自然的繁體中文回答，除非使用者明確要求其他語言。",
}


def _language_instruction(response_language: str | None) -> str:
    key = (response_language or "id").strip()
    return _LANGUAGE_INSTRUCTIONS.get(key, _LANGUAGE_INSTRUCTIONS["id"])


def _wants_knowledge(message: str, section_key: str, budget: ContextBudget) -> bool:
    lower = (message or "").lower()
    if budget.knowledge_chunks <= 0:
        return False
    return section_key == "ai_knowledge" or any(t in lower for t in _KNOWLEDGE_TRIGGERS) or bool(lower.strip())


def build(
    db: Session,
    principal: Principal,
    *,
    message: str,
    section_key: Optional[str] = "general",
    thinking_mode: Optional[str] = "balance",
    session_id: Optional[uuid.UUID] = None,
    response_language: Optional[str] = None,
) -> dict:
    """Return {'context': str|None, 'meta': dict} for a model request."""
    from app.services import ai_tools_registry, knowledge_service, memory_context_builder

    key = (section_key or "general").strip() or "general"
    budget = _budget(thinking_mode)
    blocks: list[str] = []
    meta = {
        "section_key": key,
        "thinking_mode": normalize_thinking(thinking_mode),
        "context_budget": {
            "recent_messages": budget.recent_messages,
            "knowledge_chunks": budget.knowledge_chunks,
            "include_old_search": budget.include_old_search,
        },
        "used_memory": False,
        "used_knowledge": False,
        "knowledge_sources": [],
        "response_language": response_language or "id",
        "active_tools": ai_tools_registry.active_tool_names_for_section(key),
    }

    blocks.append("[AllHaven Context Packet]")
    blocks.append(f"Mode: {budget.label}. {budget.instruction}")
    blocks.append("Preferred response language: " + _language_instruction(response_language))
    blocks.append(f"Active section: {key}. {_SECTION_HINTS.get(key, _SECTION_HINTS['general'])}")
    if meta["active_tools"]:
        blocks.append("Active tool priority: " + ", ".join(meta["active_tools"][:18]))

    summary = _summary(db, principal, session_id)
    if summary and normalize_thinking(thinking_mode) in ("thinking", "deep"):
        blocks.append("[Conversation Summary]")
        blocks.append(summary[:1800])

    memory_block = memory_context_builder.build(db, principal, message, key)
    if memory_block:
        meta["used_memory"] = True
        blocks.append(memory_block)

    if budget.include_old_search:
        snippets = []
        for row in _recent_messages(db, principal, session_id, budget.recent_messages):
            if row.role in ("user", "assistant") and row.content:
                snippets.append(f"{row.role}: {row.content[:260]}")
        if snippets:
            blocks.append("[Recent Conversation Snippets]")
            blocks.append("\n".join(snippets[-12:]))

    overview = knowledge_service.knowledge_overview(db, principal)
    if overview:
        blocks.append(overview)

    if _wants_knowledge(message, key, budget):
        knowledge_block, sources = knowledge_service.retrieve_context(db, principal, message, limit=budget.knowledge_chunks or 2)
        if knowledge_block:
            meta["used_knowledge"] = True
            meta["knowledge_sources"] = sources
            blocks.append(knowledge_block)

    blocks.append("[Tool and approval rules]")
    blocks.append("Read tools may run automatically. Most write/destructive tools create pending actions first; low-risk memory writes may save directly. Never claim pending actions are saved until approved.")
    blocks.append("Never store or repeat secrets/API keys as memory. Use app tools only; no SQL, shell, filesystem, or secrets access.")
    blocks.append("[Response style]")
    blocks.append("No basa-basi. Start with the direct answer/action status. Routine replies should be 1-3 short sentences unless the user asks for detail.")
    blocks.append("Adapt to the user's mode: casual chat can be warm and playful, serious work stays focused, coding gets senior engineering help, and scheduling uses task/calendar context.")
    blocks.append("[End of AllHaven Context Packet]")

    context = "\n".join(blocks).strip()
    return {"context": context if context else None, "meta": meta}
