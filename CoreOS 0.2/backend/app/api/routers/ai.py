"""AI router: sessions, messages, chat, and tool proposals.

The chat endpoint persists messages and returns an honest reply. Proposals can be
listed and rejected; there is intentionally no approve/execute endpoint in the
MVP (human-in-the-loop, no autonomous execution).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.ai import (
    ChatRequest,
    ChatResponse,
    MessageOut,
    ProposalOut,
    SessionCreate,
    SessionOut,
)
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/sessions")
def list_sessions(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    sessions = ai_service.list_sessions(db, principal)
    return success_response([SessionOut.model_validate(s) for s in sessions], "Sessions retrieved")


@router.post("/sessions")
def create_session(
    payload: SessionCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    session = ai_service.create_session(db, principal, payload.title)
    return success_response(SessionOut.model_validate(session), "Session created")


@router.get("/sessions/{session_id}")
def get_session(
    session_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    session = ai_service.get_session(db, principal, session_id)
    return success_response(SessionOut.model_validate(session), "Session retrieved")


@router.get("/sessions/{session_id}/messages")
def list_messages(
    session_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    messages = ai_service.list_messages(db, principal, session_id)
    return success_response([MessageOut.model_validate(m) for m in messages], "Messages retrieved")


@router.post("/chat")
def chat(
    payload: ChatRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    result = ai_service.chat(
        db, principal, message=payload.message, session_id=payload.session_id
    )
    data = ChatResponse(
        session_id=result["session_id"],
        reply=MessageOut.model_validate(result["reply"]),
        ai_configured=result["ai_configured"],
    )
    return success_response(data, "Message processed")


@router.get("/proposals")
def list_proposals(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    proposals = ai_service.list_proposals(db, principal)
    return success_response(
        [ProposalOut.model_validate(p) for p in proposals], "Pending proposals retrieved"
    )


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(
    proposal_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    proposal = ai_service.reject_proposal(db, principal, proposal_id)
    return success_response(ProposalOut.model_validate(proposal), "Proposal rejected")
