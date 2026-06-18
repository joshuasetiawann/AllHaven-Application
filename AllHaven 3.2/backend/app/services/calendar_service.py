"""Local calendar event CRUD (workspace-scoped, soft delete)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.principal import Principal
from app.domain.calendar import CalendarEvent


def list_events(
    db: Session,
    principal: Principal,
    *,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[CalendarEvent]:
    stmt = select(CalendarEvent).where(
        CalendarEvent.workspace_id == principal.workspace_id,
        CalendarEvent.is_deleted.is_(False),
    )
    if start is not None:
        stmt = stmt.where(CalendarEvent.start_at >= start)
    if end is not None:
        stmt = stmt.where(CalendarEvent.start_at <= end)
    return list(db.scalars(stmt.order_by(CalendarEvent.start_at.asc())).all())


def _get(db: Session, principal: Principal, event_id: uuid.UUID) -> CalendarEvent:
    event = db.scalar(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.workspace_id == principal.workspace_id,
            CalendarEvent.is_deleted.is_(False),
        )
    )
    if not event:
        raise NotFoundError("Calendar event not found.")
    return event


def create_event(db: Session, principal: Principal, data: dict) -> CalendarEvent:
    if data.get("end_at") and data.get("start_at") and data["end_at"] < data["start_at"]:
        raise ValidationAppError("Event end must be after its start.")
    event = CalendarEvent(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        title=data["title"],
        description=data.get("description"),
        location=data.get("location"),
        start_at=data["start_at"],
        end_at=data.get("end_at"),
        all_day=bool(data.get("all_day", False)),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_event(db: Session, principal: Principal, event_id: uuid.UUID, data: dict) -> CalendarEvent:
    event = _get(db, principal, event_id)
    for field in ("title", "description", "location", "start_at", "end_at", "all_day"):
        if field in data and data[field] is not None:
            setattr(event, field, data[field])
    if event.end_at and event.end_at < event.start_at:
        raise ValidationAppError("Event end must be after its start.")
    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, principal: Principal, event_id: uuid.UUID) -> None:
    event = _get(db, principal, event_id)
    event.is_deleted = True
    db.commit()
