"""Settings router: integration status (honest, secret-free)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.settings import IntegrationsOut, IntegrationStatus
from app.services.integration_status_service import get_integration_status

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/integrations")
def integrations(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    statuses = get_integration_status(db)
    data = IntegrationsOut(
        integrations=[IntegrationStatus(**item) for item in statuses]
    )
    return success_response(data, "Integration status")
