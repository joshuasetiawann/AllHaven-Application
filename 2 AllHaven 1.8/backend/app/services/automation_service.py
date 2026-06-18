"""Local automation definition CRUD (workspace-scoped, soft delete).

AllHaven never executes these definitions in the MVP — they are disabled-safe
drafts. Execution would require a safely configured, verified n8n connection.
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.principal import Principal
from app.domain.automations import Automation


def list_automations(db: Session, principal: Principal) -> List[Automation]:
    stmt = (
        select(Automation)
        .where(Automation.workspace_id == principal.workspace_id, Automation.is_deleted.is_(False))
        .order_by(Automation.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def _get(db: Session, principal: Principal, automation_id: uuid.UUID) -> Automation:
    row = db.scalar(
        select(Automation).where(
            Automation.id == automation_id,
            Automation.workspace_id == principal.workspace_id,
            Automation.is_deleted.is_(False),
        )
    )
    if not row:
        raise NotFoundError("Automation not found.")
    return row


def create_automation(db: Session, principal: Principal, data: dict) -> Automation:
    row = Automation(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        name=data["name"],
        description=data.get("description"),
        trigger_type=data.get("trigger_type") or "manual",
        action_type=data.get("action_type") or "noop",
        config=data.get("config") or {},
        enabled=False,  # created disabled-safe; AllHaven does not run it
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_automation(db: Session, principal: Principal, automation_id: uuid.UUID, data: dict) -> Automation:
    row = _get(db, principal, automation_id)
    for field in ("name", "description", "trigger_type", "action_type", "config", "enabled"):
        if field in data and data[field] is not None:
            setattr(row, field, data[field])
    db.commit()
    db.refresh(row)
    return row


def delete_automation(db: Session, principal: Principal, automation_id: uuid.UUID) -> None:
    row = _get(db, principal, automation_id)
    row.is_deleted = True
    db.commit()
