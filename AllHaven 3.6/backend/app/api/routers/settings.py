"""Settings router: integration configuration, testing, and status.

All endpoints are authenticated and workspace-scoped. Secrets are stored
encrypted server-side and never returned — only masked previews.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.integrations import IntegrationUpdateRequest
from app.services import integration_config_service as svc
from app.services.local_first_sync import sync_after_write

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/integrations")
def list_integrations(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(
        {"integrations": svc.list_integrations(db, principal)}, "Integration status"
    )


@router.get("/integrations/{provider_id}")
def get_integration(
    provider_id: str,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(svc.get_integration(db, principal, provider_id), "Integration config")


@router.put("/integrations/{provider_id}")
def update_integration(
    provider_id: str,
    payload: IntegrationUpdateRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    view = svc.upsert_integration(
        db, principal, provider_id, public=payload.public_config, secrets=payload.secrets
    )
    sync_after_write(db, principal)
    return success_response(view, "Integration saved")


@router.post("/integrations/{provider_id}/test")
def test_integration(
    provider_id: str,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    view = svc.test_integration(db, principal, provider_id)
    sync_after_write(db, principal)
    return success_response(view, "Connection tested")


@router.post("/integrations/{provider_id}/enable")
def enable_integration(
    provider_id: str,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    view = svc.set_enabled(db, principal, provider_id, True)
    sync_after_write(db, principal)
    return success_response(view, "Integration enabled")


@router.post("/integrations/{provider_id}/disable")
def disable_integration(
    provider_id: str,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    view = svc.set_enabled(db, principal, provider_id, False)
    sync_after_write(db, principal)
    return success_response(view, "Integration disabled")


@router.delete("/integrations/{provider_id}")
def clear_integration(
    provider_id: str,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    view = svc.clear_integration(db, principal, provider_id)
    sync_after_write(db, principal)
    return success_response(view, "Integration cleared")
