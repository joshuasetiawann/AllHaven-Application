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
from app.domain.ai import AiToolProposal, ChatMessage, ChatSession
from app.services import ai_provider_router
from app.services.audit_service import write_audit


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
    db: Session, principal: Principal, title: Optional[str] = None
) -> ChatSession:
    session = ChatSession(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        title=title,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


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
            title=message[:60],
        )
        db.add(session)
        db.flush()

    user_message = ChatMessage(
        workspace_id=principal.workspace_id,
        session_id=session.id,
        role="user",
        content=message,
    )
    db.add(user_message)
    db.flush()

    result = ai_provider_router.run_chat(
        db, principal, messages=[{"role": "user", "content": message}], provider_id=provider_id
    )
    assistant_message = ChatMessage(
        workspace_id=principal.workspace_id,
        session_id=session.id,
        role="assistant",
        content=result["content"],
        meta={
            "source": "provider" if result["ok"] else "system",
            "provider_id": result.get("provider_id"),
            "blocked": result.get("blocked", False),
            "ok": result["ok"],
            "error": result.get("error") or None,
        },
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

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
