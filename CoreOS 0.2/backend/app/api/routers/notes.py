"""Notes router (thin: delegates to note_service)."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.notes import NoteCreate, NoteOut, NoteUpdate
from app.services import note_service

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("")
def list_notes(
    q: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    notes = note_service.list_notes(db, principal, q=q, tag=tag, limit=limit, offset=offset)
    return success_response([NoteOut.model_validate(n) for n in notes], "Notes retrieved")


@router.post("")
def create_note(
    payload: NoteCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    note = note_service.create_note(db, principal, payload)
    return success_response(NoteOut.model_validate(note), "Note created")


@router.get("/{note_id}")
def get_note(
    note_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    note = note_service.get_note(db, principal, note_id)
    return success_response(NoteOut.model_validate(note), "Note retrieved")


@router.patch("/{note_id}")
def update_note(
    note_id: uuid.UUID,
    payload: NoteUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    note = note_service.update_note(db, principal, note_id, payload)
    return success_response(NoteOut.model_validate(note), "Note updated")


@router.delete("/{note_id}")
def delete_note(
    note_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    note_service.delete_note(db, principal, note_id)
    return success_response({"id": str(note_id)}, "Note deleted")
