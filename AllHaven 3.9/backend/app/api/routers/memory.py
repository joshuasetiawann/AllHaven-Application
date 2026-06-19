"""AI Memory endpoints: CRUD, suggestions, settings, and optional Supabase sync."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.memory import (
    MemoryCreate,
    MemoryOut,
    MemorySettingsOut,
    MemorySettingsUpdate,
    MemoryUpdate,
    SuggestionOut,
)
from app.services import ai_settings_service, memory_service
from app.services.local_first_sync import sync_after_write
from app.services.memory_service import MAX_MEMORIES_PER_WORKSPACE

router = APIRouter(prefix="/ai/memory", tags=["ai-memory"])


@router.get("")
def list_memories(
    category: Optional[str] = Query(default=None),
    status: str = Query(default="active"),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    rows = memory_service.list_memories(db, principal, category=category, status=status)
    return success_response([MemoryOut.model_validate(m) for m in rows], "Memories retrieved")


@router.post("")
def create_memory(
    payload: MemoryCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    m = memory_service.create_memory(
        db, principal,
        category=payload.category,
        title=payload.title,
        content=payload.content,
        sensitivity=payload.sensitivity,
        source="manual",
    )
    db.commit()
    db.refresh(m)
    sync_after_write(db, principal)
    return success_response(MemoryOut.model_validate(m), "Memory created")


@router.get("/search")
def search_memories(
    q: str = Query(min_length=1),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    rows = memory_service.search_memories(db, principal, q)
    return success_response([MemoryOut.model_validate(m) for m in rows], "Search results")


@router.get("/suggestions")
def list_suggestions(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    rows = memory_service.list_suggestions(db, principal)
    return success_response([SuggestionOut.model_validate(s) for s in rows], "Suggestions retrieved")


@router.get("/settings")
def get_memory_settings(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    settings = ai_settings_service.get_memory_settings(db, principal)
    return success_response(MemorySettingsOut(**settings), "Memory settings")


@router.put("/settings")
def update_memory_settings(
    payload: MemorySettingsUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    settings = ai_settings_service.set_memory_settings(db, principal, updates)
    sync_after_write(db, principal)
    return success_response(MemorySettingsOut(**settings), "Memory settings saved")


@router.post("/clear")
def clear_all_memories(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Delete ALL memories for this workspace regardless of status. Irreversible."""
    count = memory_service.clear_all_memories(db, principal)
    sync_after_write(db, principal)
    return success_response({"deleted": count}, "All memories cleared")


@router.post("/sync/supabase")
def sync_supabase(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Trigger a Supabase memory sync (requires Task 16 — supabase_sync_service).

    Returns a graceful 'not available' response when the sync service has not been
    implemented yet (ImportError), so this router remains importable before Task 16.
    """
    try:
        from app.services import supabase_sync_service  # noqa: PLC0415  (lazy — Task 16)
    except ImportError:
        return success_response(
            {"status": "not_available", "message": "Supabase sync service is not yet configured."},
            "Supabase sync not available",
        )
    result = supabase_sync_service.sync_all(db, principal)
    return success_response(result, "Supabase sync triggered")


@router.post("/suggestions/{suggestion_id}/approve")
def approve_suggestion(
    suggestion_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    m = memory_service.approve_suggestion(db, principal, suggestion_id)
    db.commit()
    db.refresh(m)
    sync_after_write(db, principal)
    return success_response(MemoryOut.model_validate(m), "Suggestion approved")


@router.post("/suggestions/{suggestion_id}/reject")
def reject_suggestion(
    suggestion_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    memory_service.reject_suggestion(db, principal, suggestion_id)
    db.commit()
    sync_after_write(db, principal)
    return success_response({"id": str(suggestion_id)}, "Suggestion rejected")


@router.patch("/{memory_id}")
def update_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    m = memory_service.update_memory(
        db, principal, memory_id,
        title=payload.title, content=payload.content, category=payload.category,
    )
    db.commit()
    db.refresh(m)
    sync_after_write(db, principal)
    return success_response(MemoryOut.model_validate(m), "Memory updated")


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    memory_service.delete_memory(db, principal, memory_id)
    db.commit()
    sync_after_write(db, principal)
    return success_response({"id": str(memory_id)}, "Memory deleted")


@router.post("/{memory_id}/enable")
def enable_memory(
    memory_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    m = memory_service.update_memory(db, principal, memory_id, enabled=True)
    db.commit()
    db.refresh(m)
    sync_after_write(db, principal)
    return success_response(MemoryOut.model_validate(m), "Memory enabled")


@router.post("/{memory_id}/disable")
def disable_memory(
    memory_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    m = memory_service.update_memory(db, principal, memory_id, enabled=False)
    db.commit()
    db.refresh(m)
    sync_after_write(db, principal)
    return success_response(MemoryOut.model_validate(m), "Memory disabled")
