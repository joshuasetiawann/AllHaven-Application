"""n8n router: read + manage the workspace's live n8n workflows.

Backed by the connected n8n instance (Base URL + API key in Settings). The API
key stays server-side; only workflow id/name/active state is returned.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.services import n8n_service

router = APIRouter(prefix="/n8n", tags=["n8n"])


class SetActiveRequest(BaseModel):
    active: bool


@router.get("/workflows")
def list_workflows(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(n8n_service.list_workflows(db, principal), "n8n workflows")


@router.post("/workflows/{workflow_id}/active")
def set_active(
    workflow_id: str,
    payload: SetActiveRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    result = n8n_service.set_active(db, principal, workflow_id, payload.active)
    return success_response(result, "Workflow updated")
