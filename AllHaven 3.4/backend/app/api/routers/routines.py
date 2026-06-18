"""Routines router: schedule/routine CRUD backed by local calendar events."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.calendar import CalendarEventCreate, CalendarEventOut, CalendarEventUpdate
from app.services import calendar_service as svc
from app.services.local_first_sync import sync_after_write

router = APIRouter(prefix="/routines", tags=["routines"])


@router.get("/events")
def list_routines(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    events = svc.list_events(db, principal, start=start, end=end)
    return success_response([CalendarEventOut.model_validate(e) for e in events], "Routines")


@router.post("/events")
def create_routine(
    payload: CalendarEventCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    event = svc.create_event(db, principal, payload.model_dump())
    sync_after_write(db, principal)
    return success_response(CalendarEventOut.model_validate(event), "Routine created")


@router.put("/events/{event_id}")
def update_routine(
    event_id: uuid.UUID,
    payload: CalendarEventUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    event = svc.update_event(db, principal, event_id, payload.model_dump(exclude_unset=True))
    sync_after_write(db, principal)
    return success_response(CalendarEventOut.model_validate(event), "Routine updated")


@router.delete("/events/{event_id}")
def delete_routine(
    event_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    svc.delete_event(db, principal, event_id)
    sync_after_write(db, principal)
    return success_response({"id": str(event_id)}, "Routine deleted")
