"""Automations router: local definition CRUD (workspace-scoped, no execution)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.automations import AutomationCreate, AutomationOut, AutomationUpdate
from app.services import automation_service as svc
from app.services.local_first_sync import sync_after_write

router = APIRouter(prefix="/automations", tags=["automations"])


@router.get("")
def list_automations(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    rows = svc.list_automations(db, principal)
    return success_response([AutomationOut.model_validate(r) for r in rows], "Automations")


@router.post("")
def create_automation(
    payload: AutomationCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    row = svc.create_automation(db, principal, payload.model_dump())
    sync_after_write(db, principal)
    return success_response(AutomationOut.model_validate(row), "Automation created")


@router.put("/{automation_id}")
def update_automation(
    automation_id: uuid.UUID,
    payload: AutomationUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    row = svc.update_automation(db, principal, automation_id, payload.model_dump(exclude_unset=True))
    sync_after_write(db, principal)
    return success_response(AutomationOut.model_validate(row), "Automation updated")


@router.delete("/{automation_id}")
def delete_automation(
    automation_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    svc.delete_automation(db, principal, automation_id)
    sync_after_write(db, principal)
    return success_response({"id": str(automation_id)}, "Automation deleted")
