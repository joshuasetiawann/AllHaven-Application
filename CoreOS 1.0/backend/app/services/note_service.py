"""Note service: workspace-scoped CRUD with soft delete and audit logging."""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.principal import Principal
from app.domain.notes import Note
from app.schemas.notes import NoteCreate, NoteUpdate
from app.services.audit_service import snapshot, write_audit


def list_notes(
    db: Session,
    principal: Principal,
    *,
    q: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Note]:
    stmt = select(Note).where(
        Note.workspace_id == principal.workspace_id,
        Note.is_deleted.is_(False),
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Note.title.ilike(like))
    stmt = stmt.order_by(Note.is_pinned.desc(), Note.updated_at.desc()).limit(limit).offset(offset)
    notes = list(db.scalars(stmt).all())
    # Tag filtering is done in Python to stay portable across PostgreSQL/SQLite.
    if tag:
        tag = tag.strip()
        notes = [n for n in notes if tag in (n.tags or [])]
    return notes


def get_note(db: Session, principal: Principal, note_id: uuid.UUID) -> Note:
    note = db.scalar(
        select(Note).where(
            Note.id == note_id,
            Note.workspace_id == principal.workspace_id,
            Note.is_deleted.is_(False),
        )
    )
    if not note:
        raise NotFoundError("Note not found.")
    return note


def create_note(db: Session, principal: Principal, data: NoteCreate) -> Note:
    note = Note(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        title=data.title,
        content=data.content,
        tags=data.tags,
        is_pinned=data.is_pinned,
    )
    db.add(note)
    db.flush()
    write_audit(
        db,
        action="CREATE",
        entity_name="note",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=note.id,
        after=snapshot(note),
    )
    db.commit()
    db.refresh(note)
    return note


def update_note(db: Session, principal: Principal, note_id: uuid.UUID, data: NoteUpdate) -> Note:
    note = get_note(db, principal, note_id)
    before = snapshot(note)

    fields = data.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(note, key, value)
    note.updated_by = principal.user_id

    db.flush()
    write_audit(
        db,
        action="UPDATE",
        entity_name="note",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=note.id,
        before=before,
        after=snapshot(note),
    )
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, principal: Principal, note_id: uuid.UUID) -> None:
    note = get_note(db, principal, note_id)
    before = snapshot(note)
    note.is_deleted = True
    note.updated_by = principal.user_id
    db.flush()
    write_audit(
        db,
        action="DELETE",
        entity_name="note",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=note.id,
        before=before,
    )
    db.commit()
