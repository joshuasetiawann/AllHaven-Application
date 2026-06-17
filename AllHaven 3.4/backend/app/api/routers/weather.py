"""Weather router: saved locations + honest current-weather fetch."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.weather import WeatherLocationCreate, WeatherLocationOut
from app.services import weather_service as svc
from app.services.local_first_sync import sync_after_write

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/locations")
def list_locations(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    rows = svc.list_locations(db, principal)
    return success_response([WeatherLocationOut.model_validate(r) for r in rows], "Weather locations")


@router.post("/locations")
def add_location(
    payload: WeatherLocationCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    row = svc.add_location(db, principal, payload.name, payload.is_default)
    sync_after_write(db, principal)
    return success_response(WeatherLocationOut.model_validate(row), "Location saved")


@router.delete("/locations/{location_id}")
def delete_location(
    location_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    svc.delete_location(db, principal, location_id)
    sync_after_write(db, principal)
    return success_response({"id": str(location_id)}, "Location removed")


@router.get("/current")
def current_weather(
    location: Optional[str] = None,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(svc.current_weather(db, principal, location), "Current weather")
