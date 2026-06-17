"""AI router: sessions, messages, chat, and tool proposals.

The chat endpoint persists messages and returns an honest reply. Proposals can be
listed and rejected; there is intentionally no approve/execute endpoint in the
MVP (human-in-the-loop, no autonomous execution).
"""

from __future__ import annotations

import uuid
from typing import Optional

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
from pydantic import BaseModel

from app.schemas.ai_providers import AiProviderUpdateRequest
from app.services import ai_policy_service, ai_provider_router, ai_service


class AiPolicyUpdate(BaseModel):
    allow_external: Optional[bool] = None
    default_provider: Optional[str] = None

router = APIRouter(prefix="/ai", tags=["ai"])


# --- AI policy ------------------------------------------------------------


@router.get("/policy")
def get_policy(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(ai_policy_service.get_policy(db, principal), "AI policy")


@router.put("/policy")
def update_policy(
    payload: AiPolicyUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    data = ai_policy_service.set_policy(
        db,
        principal,
        allow_external=payload.allow_external,
        default_provider=payload.default_provider,
    )
    return success_response(data, "AI policy updated")


# --- AI providers ---------------------------------------------------------


@router.get("/providers")
def list_providers(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(
        {"providers": ai_provider_router.list_providers(db, principal)}, "AI providers"
    )


@router.put("/providers/{provider_id}")
def update_provider(
    provider_id: str,
    payload: AiProviderUpdateRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    view = ai_provider_router.upsert_provider(
        db,
        principal,
        provider_id,
        public=payload.public_config,
        secrets=payload.secrets,
        default_model=payload.default_model,
        privacy_mode=payload.privacy_mode,
        system_prompt=payload.system_prompt,
        temperature=payload.temperature,
        enabled=payload.enabled,
    )
    return success_response(view, "AI provider saved")


@router.post("/providers/{provider_id}/test")
def test_provider(
    provider_id: str,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(ai_provider_router.test_provider(db, principal, provider_id), "Provider tested")


@router.post("/providers/{provider_id}/enable")
def enable_provider(
    provider_id: str,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(ai_provider_router.set_enabled(db, principal, provider_id, True), "Provider enabled")


@router.post("/providers/{provider_id}/disable")
def disable_provider(
    provider_id: str,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(ai_provider_router.set_enabled(db, principal, provider_id, False), "Provider disabled")


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
        db,
        principal,
        message=payload.message,
        session_id=payload.session_id,
        provider_id=payload.provider_id,
    )
    data = ChatResponse(
        session_id=result["session_id"],
        reply=MessageOut.model_validate(result["reply"]),
        ai_configured=result["ai_configured"],
        provider_id=result.get("provider_id"),
        blocked=result.get("blocked", False),
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
