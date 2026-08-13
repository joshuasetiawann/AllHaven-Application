"""Local routine event CRUD (workspace-scoped, soft delete).

Despite the historical module name, this service stores Routine data in the
local database only. It does not call Google Calendar.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.principal import Principal
from app.domain.calendar import CalendarEvent

ALLOWED_PERIODS = {"morning", "afternoon", "evening"}
ALLOWED_REPEAT_RULES = {"once", "daily", "weekly", "monthly"}
ALLOWED_REPEAT_DAYS = {"sun", "mon", "tue", "wed", "thu", "fri", "sat"}


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


def _period_from_start(start_at: datetime | None) -> str | None:
    if start_at is None:
        return None
    hour = start_at.hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    return "evening"


def _normalize_repeat_days(days: object) -> list[str] | None:
    if days is None:
        return None
    if not isinstance(days, list):
        raise ValidationAppError("Repeat days must be a list.")
    cleaned: list[str] = []
    for raw in days:
        day = str(raw).strip().lower()
        if day not in ALLOWED_REPEAT_DAYS:
            raise ValidationAppError("Repeat days must use sun, mon, tue, wed, thu, fri, sat.")
        if day not in cleaned:
            cleaned.append(day)
    return cleaned


def _normalize_data(data: dict, *, start_at: datetime | None = None) -> dict:
    normalized = dict(data)
    if "repeat_rule" in normalized:
        repeat_rule = normalized.get("repeat_rule") or "once"
        if repeat_rule not in ALLOWED_REPEAT_RULES:
            raise ValidationAppError("Repeat rule must be once, daily, weekly, or monthly.")
        normalized["repeat_rule"] = repeat_rule
    if "repeat_days" in normalized:
        normalized["repeat_days"] = _normalize_repeat_days(normalized.get("repeat_days"))
    if "time_period" in normalized:
        period = normalized.get("time_period")
        if period is not None and period not in ALLOWED_PERIODS:
            raise ValidationAppError("Time period must be morning, afternoon, or evening.")
    elif start_at is not None:
        normalized["time_period"] = _period_from_start(start_at)
    return normalized


def _build_event(principal: Principal, data: dict) -> CalendarEvent:
    """Validate + normalize one event and return an UNSAVED CalendarEvent.

    Raises ``ValidationAppError`` on bad input before any DB write, which lets
    callers build a whole batch first and only persist once every item is valid.
    """
    data = _normalize_data(data, start_at=data.get("start_at"))
    if not str(data.get("title") or "").strip():
        raise ValidationAppError("Routine title is required.")
    if data.get("end_at") and data.get("start_at") and data["end_at"] < data["start_at"]:
        raise ValidationAppError("Event end must be after its start.")
    return CalendarEvent(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        title=data["title"],
        description=data.get("description"),
        location=data.get("location"),
        start_at=data["start_at"],
        end_at=data.get("end_at"),
        all_day=bool(data.get("all_day", False)),
        time_period=data.get("time_period"),
        repeat_rule=data.get("repeat_rule") or "once",
        repeat_days=data.get("repeat_days") or [],
        icon=data.get("icon") or "star",
        color=data.get("color") or "cyan",
        # Cross-device idempotency stamp from an approved proposal (None otherwise).
        dedup_key=data.get("dedup_key"),
    )


def create_event(db: Session, principal: Principal, data: dict) -> CalendarEvent:
    event = _build_event(principal, data)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_events_batch(db: Session, principal: Principal, items: list[dict]) -> List[CalendarEvent]:
    """Atomically create many routines: validate ALL first, then insert once.

    If any item is invalid, nothing is saved (the build step raises before any
    ``db.add``), so the caller never ends up with a partially-applied batch.
    """
    if not items:
        raise ValidationAppError("No routines to save.")
    if len(items) > 50:
        raise ValidationAppError("Cannot save more than 50 routines at once.")
    # Build (and validate) every event before touching the session — atomicity.
    events = [_build_event(principal, dict(item)) for item in items]
    db.add_all(events)
    db.commit()
    for event in events:
        db.refresh(event)
    return events


def update_event(db: Session, principal: Principal, event_id: uuid.UUID, data: dict) -> CalendarEvent:
    event = _get(db, principal, event_id)
    candidate_start = data.get("start_at") if "start_at" in data else None
    data = _normalize_data(data, start_at=candidate_start)
    for field in ("title", "start_at", "all_day", "repeat_rule"):
        if field in data and data[field] is not None:
            setattr(event, field, data[field])
    for field in ("description", "location", "end_at", "time_period", "repeat_days", "icon", "color"):
        if field in data:
            setattr(event, field, data[field])
    if not event.repeat_rule:
        event.repeat_rule = "once"
    if event.repeat_days is None:
        event.repeat_days = []
    if event.end_at and event.end_at < event.start_at:
        raise ValidationAppError("Event end must be after its start.")
    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, principal: Principal, event_id: uuid.UUID) -> None:
    event = _get(db, principal, event_id)
    event.is_deleted = True
    db.commit()
