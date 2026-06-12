"""AI Knowledge ingestion, indexing, and keyword retrieval."""

from __future__ import annotations

import csv
import io
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Iterable, List

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.principal import Principal
from app.domain.ai_knowledge import AiKnowledgeChunk, AiKnowledgeDocument

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".csv"}
MAX_KNOWLEDGE_UPLOAD_BYTES = 25 * 1024 * 1024
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 160
MAX_SEARCH_CANDIDATES = 500

_WORD_RE = re.compile(r"[A-Za-z0-9_\-]{3,}")


def _safe_basename(filename: str) -> str:
    base = os.path.basename((filename or "").replace("\\", "/")).strip()
    base = base.replace("..", "").strip(". ")
    return base or "document"


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_text(filename: str, mime_type: str, data: bytes) -> tuple[str | None, str | None]:
    ext = os.path.splitext(filename.lower())[1]
    if ext in {".txt", ".md"} or mime_type.startswith("text/"):
        return _decode_text(data), None
    if ext == ".csv" or mime_type == "text/csv":
        text = _decode_text(data)
        try:
            rows = csv.reader(io.StringIO(text))
            return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows), None
        except csv.Error:
            return text, None
    if ext in {".pdf", ".docx"}:
        return None, f"{ext} parser is not installed yet; document is stored but not indexable."
    return None, "File type is stored but not indexable yet. Supported MVP types: .txt, .md, .csv."


def _chunks(text: str) -> Iterable[str]:
    normalized = "\n".join(line.rstrip() for line in (text or "").splitlines()).strip()
    if not normalized:
        return []
    out: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + CHUNK_SIZE)
        chunk = normalized[start:end].strip()
        if chunk:
            out.append(chunk)
        if end >= len(normalized):
            break
        start = max(0, end - CHUNK_OVERLAP)
    return out


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _WORD_RE.finditer(text or "")}


def _score(query_tokens: set[str], query: str, content: str) -> float:
    if not query_tokens:
        return 0.0
    content_lower = content.lower()
    content_tokens = _tokens(content_lower)
    overlap = len(query_tokens & content_tokens)
    phrase_bonus = 2 if query.lower() in content_lower else 0
    return float(overlap + phrase_bonus) / max(1, len(query_tokens))


def list_documents(db: Session, principal: Principal) -> List[AiKnowledgeDocument]:
    stmt = (
        select(AiKnowledgeDocument)
        .where(AiKnowledgeDocument.workspace_id == principal.workspace_id)
        .order_by(AiKnowledgeDocument.updated_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_document(db: Session, principal: Principal, document_id: uuid.UUID) -> AiKnowledgeDocument:
    row = db.scalar(
        select(AiKnowledgeDocument).where(
            AiKnowledgeDocument.id == document_id,
            AiKnowledgeDocument.workspace_id == principal.workspace_id,
        )
    )
    if not row:
        raise NotFoundError("Knowledge document not found.")
    return row


def create_document_from_upload(
    db: Session, principal: Principal, *, filename: str, mime_type: str, data: bytes, title: str | None = None
) -> AiKnowledgeDocument:
    if not data:
        raise ValidationAppError("Uploaded knowledge document is empty.")
    if len(data) > MAX_KNOWLEDGE_UPLOAD_BYTES:
        raise ValidationAppError("Knowledge document exceeds the 25 MB ingestion limit.")

    safe = _safe_basename(filename)
    row = AiKnowledgeDocument(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        title=(title or os.path.splitext(safe)[0] or safe)[:255],
        filename=safe,
        mime_type=mime_type or "application/octet-stream",
        size_bytes=len(data),
        status="indexing",
        chunk_count=0,
        meta={},
    )
    db.add(row)
    db.flush()

    text, error = _extract_text(safe, row.mime_type, data)
    if error:
        row.status = "uploaded"
        row.error_message = error
        db.flush()
        return row
    if not text or not text.strip():
        row.status = "failed"
        row.error_message = "No readable text could be extracted from this document."
        db.flush()
        return row

    pieces = list(_chunks(text))
    if not pieces:
        row.status = "failed"
        row.error_message = "No indexable chunks were produced from this document."
        db.flush()
        return row

    for idx, content in enumerate(pieces):
        db.add(AiKnowledgeChunk(
            workspace_id=principal.workspace_id,
            document_id=row.id,
            chunk_index=idx,
            content=content,
            meta={"filename": safe},
        ))
    row.status = "indexed"
    row.chunk_count = len(pieces)
    row.last_indexed_at = datetime.now(timezone.utc)
    row.error_message = None
    db.flush()
    return row


def delete_document(db: Session, principal: Principal, document_id: uuid.UUID) -> None:
    row = get_document(db, principal, document_id)
    db.execute(delete(AiKnowledgeChunk).where(
        AiKnowledgeChunk.workspace_id == principal.workspace_id,
        AiKnowledgeChunk.document_id == row.id,
    ))
    db.delete(row)
    db.flush()


def reindex_document(db: Session, principal: Principal, document_id: uuid.UUID) -> AiKnowledgeDocument:
    row = get_document(db, principal, document_id)
    old_chunks = list(db.scalars(
        select(AiKnowledgeChunk)
        .where(AiKnowledgeChunk.workspace_id == principal.workspace_id, AiKnowledgeChunk.document_id == row.id)
        .order_by(AiKnowledgeChunk.chunk_index.asc())
    ).all())
    if not old_chunks:
        row.status = "uploaded"
        row.error_message = row.error_message or "No source text is available to re-index this document."
        db.flush()
        return row
    text = "\n".join(c.content for c in old_chunks)
    db.execute(delete(AiKnowledgeChunk).where(
        AiKnowledgeChunk.workspace_id == principal.workspace_id,
        AiKnowledgeChunk.document_id == row.id,
    ))
    pieces = list(_chunks(text))
    for idx, content in enumerate(pieces):
        db.add(AiKnowledgeChunk(
            workspace_id=principal.workspace_id,
            document_id=row.id,
            chunk_index=idx,
            content=content,
            meta={"filename": row.filename, "reindexed": True},
        ))
    row.status = "indexed" if pieces else "failed"
    row.chunk_count = len(pieces)
    row.last_indexed_at = datetime.now(timezone.utc) if pieces else row.last_indexed_at
    row.error_message = None if pieces else "No chunks were produced while re-indexing."
    db.flush()
    return row


def search_knowledge(db: Session, principal: Principal, query: str, *, limit: int = 5) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []
    q_tokens = _tokens(q)
    stmt = (
        select(AiKnowledgeChunk, AiKnowledgeDocument)
        .join(AiKnowledgeDocument, AiKnowledgeDocument.id == AiKnowledgeChunk.document_id)
        .where(
            AiKnowledgeChunk.workspace_id == principal.workspace_id,
            AiKnowledgeDocument.workspace_id == principal.workspace_id,
            AiKnowledgeDocument.status == "indexed",
        )
        .order_by(AiKnowledgeDocument.updated_at.desc(), AiKnowledgeChunk.chunk_index.asc())
        .limit(MAX_SEARCH_CANDIDATES)
    )
    ranked = []
    for chunk, doc in db.execute(stmt).all():
        score = _score(q_tokens, q, chunk.content)
        if score <= 0:
            continue
        ranked.append((score, chunk, doc))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "document_id": doc.id,
            "document_title": doc.title,
            "document_filename": doc.filename,
            "chunk_id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "score": score,
            "content": chunk.content,
        }
        for score, chunk, doc in ranked[: max(1, min(limit, 10))]
    ]


def retrieve_context(db: Session, principal: Principal, query: str, *, limit: int = 3) -> tuple[str | None, list[dict]]:
    results = search_knowledge(db, principal, query, limit=limit)
    if not results:
        return None, []
    lines = ["[AI Knowledge — retrieved document context]"]
    meta = []
    for item in results:
        lines.append(f"Source: {item['document_title']} ({item['document_filename']}) chunk {item['chunk_index']}")
        lines.append(str(item["content"])[:1400])
        meta.append({
            "document_id": str(item["document_id"]),
            "title": item["document_title"],
            "filename": item["document_filename"],
            "chunk_index": item["chunk_index"],
            "score": item["score"],
        })
    lines.append("[End of AI Knowledge]")
    return "\n".join(lines), meta
