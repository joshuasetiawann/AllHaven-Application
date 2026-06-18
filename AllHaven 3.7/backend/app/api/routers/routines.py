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
from app.schemas.routine import RoutineBatchCreate, RoutineGenerateRequest
from app.services import calendar_service as svc
from app.services import routine_ai_service, supabase_sync_service
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


@router.post("/events/batch")
def create_routines_batch(
    payload: RoutineBatchCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Atomically create many routines. If any item is invalid, none are saved."""
    events = svc.create_events_batch(db, principal, [item.model_dump() for item in payload.items])
    sync_after_write(db, principal)
    return success_response(
        [CalendarEventOut.model_validate(e) for e in events],
        f"{len(events)} routines created",
    )


@router.post("/generate")
def generate_routines(
    payload: RoutineGenerateRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Generate routine DRAFTS with AI. Never saves; returns drafts for review."""
    result = routine_ai_service.generate_drafts(
        db,
        principal,
        prompt=payload.prompt,
        date=payload.date,
        period=payload.period,
        use_context=payload.use_context,
    )
    return success_response(result, "Routine drafts")


@router.get("/sync-status")
def routine_sync_status(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Supabase mirror status for the Sync summary card; falls back to local-first."""
    try:
        active = supabase_sync_service.is_enabled(db, principal)
        status = "active" if active else "local_first"
        return success_response({"status": status, "configured": bool(active)}, "Sync status")
    except Exception:
        return success_response({"status": "error", "configured": False}, "Sync status")


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
