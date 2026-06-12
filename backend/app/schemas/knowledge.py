"""AI Knowledge schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from app.schemas.common import ORMModel


class KnowledgeDocumentOut(ORMModel):
    id: uuid.UUID
    title: str
    filename: str
    mime_type: str
    size_bytes: int
    status: str
    chunk_count: int
    last_indexed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class KnowledgeChunkOut(ORMModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    meta: Optional[dict] = None
    created_at: datetime


class KnowledgeSearchResult(ORMModel):
    document_id: uuid.UUID
    document_title: str
    document_filename: str
    chunk_id: uuid.UUID
    chunk_index: int
    score: float
    content: str


class KnowledgeSearchResponse(ORMModel):
    results: list[KnowledgeSearchResult]
    count: int
