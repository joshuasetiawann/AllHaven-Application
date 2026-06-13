"""AI Knowledge router: document ingestion, indexing status, and search."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.knowledge import KnowledgeDocumentOut, KnowledgeSearchResponse
from app.services import knowledge_service
from app.services.local_first_sync import sync_after_write

router = APIRouter(prefix="/ai/knowledge", tags=["ai-knowledge"])


@router.get("/documents")
def list_documents(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    rows = knowledge_service.list_documents(db, principal)
    return success_response([KnowledgeDocumentOut.model_validate(r) for r in rows], "Knowledge documents")


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Query(default=None, max_length=255),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    data = await file.read()
    row = knowledge_service.create_document_from_upload(
        db, principal,
        filename=file.filename or "document",
        mime_type=file.content_type or "application/octet-stream",
        data=data,
        title=title,
    )
    db.commit()
    db.refresh(row)
    sync_after_write(db, principal)
    return success_response(KnowledgeDocumentOut.model_validate(row), "Knowledge document uploaded")


@router.get("/documents/{document_id}")
def get_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    row = knowledge_service.get_document(db, principal, document_id)
    return success_response(KnowledgeDocumentOut.model_validate(row), "Knowledge document")


@router.post("/documents/{document_id}/reindex")
def reindex_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    row = knowledge_service.reindex_document(db, principal, document_id)
    db.commit()
    db.refresh(row)
    sync_after_write(db, principal)
    return success_response(KnowledgeDocumentOut.model_validate(row), "Knowledge document re-indexed")


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    knowledge_service.delete_document(db, principal, document_id)
    db.commit()
    sync_after_write(db, principal)
    return success_response({"id": str(document_id)}, "Knowledge document deleted")


@router.get("/search")
def search_knowledge(
    q: str = Query(min_length=1),
    limit: int = Query(default=5, ge=1, le=10),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    results = knowledge_service.search_knowledge(db, principal, q, limit=limit)
    return success_response(KnowledgeSearchResponse(results=results, count=len(results)), "Knowledge search results")
