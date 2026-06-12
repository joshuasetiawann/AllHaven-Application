"""AI service: chat sessions/messages and tool proposals.

Human-in-the-loop policy:
    * The assistant persists messages and may surface tool *proposals*.
    * It never executes a proposal automatically. The MVP exposes listing and
      rejection only; approval/execution is intentionally not implemented.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.principal import Principal
from app.domain.ai import (
    AiAgentResponse,
    AiMultiAgentRun,
    AiToolProposal,
    ChatGroup,
    ChatMessage,
    ChatSession,
)
from app.services import ai_provider_router
from app.services.audit_service import write_audit


def _auto_title(message: str) -> str:
    """Title from the first user message, max 40 chars."""
    text = " ".join((message or "").split()).strip()
    if len(text) > 40:
        text = text[:39].rstrip() + "…"
    return text or "New Chat"


# --- groups ---------------------------------------------------------------


def list_groups(db: Session, principal: Principal) -> List[ChatGroup]:
    stmt = (
        select(ChatGroup)
        .where(ChatGroup.workspace_id == principal.workspace_id)
        .order_by(ChatGroup.created_at.asc())
    )
    return list(db.scalars(stmt).all())


def create_group(db: Session, principal: Principal, name: str) -> ChatGroup:
    group = ChatGroup(workspace_id=principal.workspace_id, created_by=principal.user_id, name=name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def _get_group(db: Session, principal: Principal, group_id: uuid.UUID) -> ChatGroup:
    group = db.scalar(
        select(ChatGroup).where(
            ChatGroup.id == group_id, ChatGroup.workspace_id == principal.workspace_id
        )
    )
    if not group:
        raise NotFoundError("Group not found.")
    return group


def update_group(db: Session, principal: Principal, group_id: uuid.UUID, name: str) -> ChatGroup:
    group = _get_group(db, principal, group_id)
    group.name = name
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, principal: Principal, group_id: uuid.UUID) -> None:
    group = _get_group(db, principal, group_id)
    # Detach conversations (don't delete them), then remove the group.
    for s in db.scalars(
        select(ChatSession).where(
            ChatSession.workspace_id == principal.workspace_id, ChatSession.group_id == group_id
        )
    ).all():
        s.group_id = None
    db.delete(group)
    db.commit()


def list_sessions(db: Session, principal: Principal) -> List[ChatSession]:
    stmt = (
        select(ChatSession)
        .where(ChatSession.workspace_id == principal.workspace_id)
        .order_by(ChatSession.updated_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_session(db: Session, principal: Principal, session_id: uuid.UUID) -> ChatSession:
    session = db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.workspace_id == principal.workspace_id,
        )
    )
    if not session:
        raise NotFoundError("Chat session not found.")
    return session


def create_session(
    db: Session,
    principal: Principal,
    title: Optional[str] = None,
    group_id: Optional[uuid.UUID] = None,
) -> ChatSession:
    if group_id is not None:
        _get_group(db, principal, group_id)  # validate ownership
    session = ChatSession(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        title=title,
        group_id=group_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def update_session(db: Session, principal: Principal, session_id: uuid.UUID, data: dict) -> ChatSession:
    """Rename a conversation and/or move it to a group (group_id=None removes it)."""
    session = get_session(db, principal, session_id)
    if "title" in data and data["title"] is not None:
        session.title = data["title"]
    if "group_id" in data:
        gid = data["group_id"]
        if gid is not None:
            _get_group(db, principal, gid)
        session.group_id = gid
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, principal: Principal, session_id: uuid.UUID) -> None:
    """Delete a conversation and all of its messages + multi-agent run records."""
    session = get_session(db, principal, session_id)
    ws = principal.workspace_id
    for msg in db.scalars(
        select(ChatMessage).where(ChatMessage.workspace_id == ws, ChatMessage.session_id == session_id)
    ).all():
        db.delete(msg)
    run_ids = [
        r.id
        for r in db.scalars(
            select(AiMultiAgentRun).where(
                AiMultiAgentRun.workspace_id == ws, AiMultiAgentRun.session_id == session_id
            )
        ).all()
    ]
    if run_ids:
        for resp in db.scalars(
            select(AiAgentResponse).where(
                AiAgentResponse.workspace_id == ws, AiAgentResponse.run_id.in_(run_ids)
            )
        ).all():
            db.delete(resp)
        for run in db.scalars(
            select(AiMultiAgentRun).where(
                AiMultiAgentRun.workspace_id == ws, AiMultiAgentRun.session_id == session_id
            )
        ).all():
            db.delete(run)
    db.delete(session)
    db.commit()


def list_messages(db: Session, principal: Principal, session_id: uuid.UUID) -> List[ChatMessage]:
    get_session(db, principal, session_id)  # ensures workspace ownership
    stmt = (
        select(ChatMessage)
        .where(
            ChatMessage.workspace_id == principal.workspace_id,
            ChatMessage.session_id == session_id,
        )
        .order_by(ChatMessage.created_at.asc())
    )
    return list(db.scalars(stmt).all())


def chat(
    db: Session,
    principal: Principal,
    *,
    message: str,
    session_id: Optional[uuid.UUID] = None,
    provider_id: Optional[str] = None,
    section_key: Optional[str] = "general",
) -> dict:
    """Persist the user message, route to the AI provider, persist the reply.

    The provider router is honest: if the selected/default provider is not
    configured, disabled, or blocked (external disabled), it returns a clear
    message instead of fake output. It never executes writes.
    """
    if session_id is not None:
        session = get_session(db, principal, session_id)
    else:
        session = ChatSession(
            workspace_id=principal.workspace_id,
            created_by=principal.user_id,
            title=_auto_title(message),
        )
        db.add(session)
        db.flush()
    # Auto-title an untitled conversation from its first user message.
    if not (session.title or "").strip():
        session.title = _auto_title(message)

    user_message = ChatMessage(
        workspace_id=principal.workspace_id,
        session_id=session.id,
        role="user",
        content=message,
    )
    db.add(user_message)
    db.flush()

    # Build memory context block (inject into system prompt).
    from app.services import ai_orchestrator, memory_context_builder, memory_extraction_service

    extra_context = memory_context_builder.build(db, principal, message, section_key)

    # Orchestrated chat: history-aware, with a safe tool loop on tool-capable
    # providers (reads execute; writes become pending approvals — never silent).
    result = ai_orchestrator.run_with_tools(
        db, principal, message=message, session_id=session.id,
        provider_id=provider_id, extra_context=extra_context,
    )
    meta = {
        "source": "provider" if result["ok"] else "system",
        "provider_id": result.get("provider_id"),
        "blocked": result.get("blocked", False),
        "ok": result["ok"],
        "error": result.get("error") or None,
    }
    if result.get("tool_calls"):
        meta["tool_calls"] = result["tool_calls"]
    if result.get("proposal_ids"):
        meta["proposal_ids"] = result["proposal_ids"]
    assistant_message = ChatMessage(
        workspace_id=principal.workspace_id,
        session_id=session.id,
        role="assistant",
        content=result["content"],
        meta=meta,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    # Trigger hybrid memory extraction (rule-based inline, LLM in background).
    # On failure the content is a system error explainer — noise to the LLM
    # extractor — so extract from the user message only (early-exit convention).
    memory_extraction_service.extract_and_commit(
        db, principal,
        user_msg=message,
        assistant_msg=result["content"] if result["ok"] else "",
        session_id=session.id,
    )

    return {
        "session_id": session.id,
        "reply": assistant_message,
        "ai_configured": result["ok"],
        "provider_id": result.get("provider_id"),
        "blocked": result.get("blocked", False),
    }


def list_proposals(db: Session, principal: Principal) -> List[AiToolProposal]:
    stmt = (
        select(AiToolProposal)
        .where(
            AiToolProposal.workspace_id == principal.workspace_id,
            AiToolProposal.status == "PENDING",
        )
        .order_by(AiToolProposal.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def reject_proposal(
    db: Session, principal: Principal, proposal_id: uuid.UUID
) -> AiToolProposal:
    proposal = db.scalar(
        select(AiToolProposal).where(
            AiToolProposal.id == proposal_id,
            AiToolProposal.workspace_id == principal.workspace_id,
        )
    )
    if not proposal:
        raise NotFoundError("Tool proposal not found.")

    proposal.status = "REJECTED"
    db.flush()
    write_audit(
        db,
        action="UPDATE",
        entity_name="ai_tool_proposal",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=proposal.id,
        after={"status": "REJECTED"},
        meta={"decision": "rejected_by_user"},
    )
    db.commit()
    db.refresh(proposal)
    return proposal
