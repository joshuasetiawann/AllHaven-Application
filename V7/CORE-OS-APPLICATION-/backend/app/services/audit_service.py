"""Audit logging service.

Audit entries are append-only and capture meaningful create/update/delete actions
across business modules.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.domain.audit import AuditLog


def _json_safe(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def snapshot(obj: Any) -> dict:
    """Return a JSON-safe dict of a model's column values."""
    if obj is None:
        return {}
    mapper = inspect(obj).mapper
    return {col.key: _json_safe(getattr(obj, col.key)) for col in mapper.column_attrs}


def write_audit(
    db: Session,
    *,
    action: str,
    entity_name: str,
    workspace_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    entity_id: Optional[uuid.UUID] = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    meta: Optional[dict] = None,
) -> AuditLog:
    """Create (but do not commit) an audit log entry."""
    log = AuditLog(
        workspace_id=workspace_id,
        user_id=user_id,
        action=action,
        entity_name=entity_name,
        entity_id=entity_id,
        before_data=before,
        after_data=after,
        meta=meta,
    )
    db.add(log)
    return log
