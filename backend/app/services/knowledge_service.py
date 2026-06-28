"""AI Knowledge ingestion, indexing, and keyword retrieval."""

from __future__ import annotations

import csv
import io
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Iterable, List
from xml.etree.ElementTree import ParseError as XmlParseError

# defusedxml refuses DTDs and entity expansion by default, so a malicious
# uploaded OOXML file cannot trigger XXE or billion-laughs entity expansion.
from defusedxml.ElementTree import fromstring as xml_fromstring
from defusedxml.common import DefusedXmlException

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.principal import Principal
from app.domain.ai_knowledge import AiKnowledgeChunk, AiKnowledgeDocument

SUPPORTED_TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml",
    ".xml", ".html", ".htm", ".css", ".scss", ".js", ".jsx", ".ts", ".tsx", ".py",
    ".rb", ".go", ".rs", ".java", ".kt", ".swift", ".c", ".h", ".cpp", ".hpp", ".cs",
    ".php", ".sql", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".env", ".ini", ".toml",
    ".cfg", ".conf", ".log", ".dockerfile", ".gitignore", ".gitattributes",
}
SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx"}
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 160
MAX_SEARCH_CANDIDATES = 500

_WORD_RE = re.compile(r"[A-Za-z0-9_\-]{3,}")
_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:gsk|pk|rk|xoxb|xoxp|ghp|gho|github_pat)_[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{12,}\b", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9._-]{20,}\b"),
    re.compile(r"\b(api[_-]?key|secret|token|password|passwd|pwd|authorization)\b\s*[:=]\s*\S+", re.IGNORECASE),
]


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


def _knowledge_upload_limit_bytes() -> int:
    mb = max(1, int(getattr(settings, "DRIVE_MAX_UPLOAD_MB", 250) or 250))
    return mb * 1024 * 1024


def _looks_like_text(data: bytes) -> bool:
    if not data:
        return False
    sample = data[:4096]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        printable = sum(1 for b in sample if b in (9, 10, 13) or 32 <= b <= 126)
        return printable / max(1, len(sample)) > 0.88


def _contains_secret(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _SECRET_PATTERNS)


def _metadata_text(filename: str, mime_type: str, size_bytes: int, reason: str) -> str:
    return (
        "[Stored AI Knowledge file metadata]\n"
        f"Filename: {filename}\n"
        f"MIME type: {mime_type or 'application/octet-stream'}\n"
        f"Size: {size_bytes} bytes\n"
        f"Indexing status: {reason}\n"
        "Text content was not extracted. The AI can reference that this file exists, "
        "but it must not claim to know the file contents until a parser is available."
    )


def _decode_pdf_literal(raw: str) -> str:
    out = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        i += 1
        if i >= len(raw):
            break
        esc = raw[i]
        if esc in "nrtbf":
            out.append({"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}[esc])
            i += 1
        elif esc in "\\()":
            out.append(esc)
            i += 1
        elif esc in "\n\r":
            while i < len(raw) and raw[i] in "\n\r":
                i += 1
        elif esc.isdigit():
            octal = esc
            i += 1
            for _ in range(2):
                if i < len(raw) and raw[i].isdigit():
                    octal += raw[i]
                    i += 1
            try:
                out.append(chr(int(octal, 8)))
            except ValueError:
                pass
        else:
            out.append(esc)
            i += 1
    return "".join(out)


def _simple_pdf_extract(data: bytes) -> str:
    """Best-effort PDF text extraction without native dependencies.

    Real-world PDFs vary a lot. If pypdf is unavailable, this handles common
    unencrypted PDFs with literal text streams and keeps the fallback honest.
    """
    import zlib

    candidates = [data]
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL):
        stream = match.group(1).strip()
        candidates.append(stream)
        try:
            candidates.append(zlib.decompress(stream))
        except zlib.error:
            pass

    parts: list[str] = []
    literal_re = re.compile(r"\((?:\\.|[^\\)])*\)")
    for blob in candidates:
        text = blob.decode("latin-1", errors="ignore")
        for match in re.finditer(r"(\((?:\\.|[^\\)])*\))\s*Tj", text, re.DOTALL):
            parts.append(_decode_pdf_literal(match.group(1)[1:-1]))
        for match in re.finditer(r"\[(.*?)\]\s*TJ", text, re.DOTALL):
            pieces = [m.group(0)[1:-1] for m in literal_re.finditer(match.group(1))]
            if pieces:
                parts.append("".join(_decode_pdf_literal(piece) for piece in pieces))
    return "\n".join(part.strip() for part in parts if part.strip())


def _extract_pdf(data: bytes) -> tuple[str | None, str | None]:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "").strip() for page in reader.pages)
        if text.strip():
            return text, None
    except Exception:
        pass

    text = _simple_pdf_extract(data)
    if text.strip():
        return text, None
    return None, "PDF text could not be extracted. The file is stored and searchable by metadata only."


def _extract_docx(data: bytes) -> tuple[str | None, str | None]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = [
                "word/document.xml",
                *[name for name in archive.namelist() if name.startswith("word/header") and name.endswith(".xml")],
                *[name for name in archive.namelist() if name.startswith("word/footer") and name.endswith(".xml")],
            ]
            parts: list[str] = []
            for name in names:
                if name not in archive.namelist():
                    continue
                root = xml_fromstring(archive.read(name))
                for node in root.iter():
                    tag = node.tag.rsplit("}", 1)[-1]
                    if tag == "t" and node.text:
                        parts.append(node.text)
                    elif tag in {"tab", "br", "cr"}:
                        parts.append("\n")
            text = " ".join(part.strip() for part in parts if part and part.strip())
            if text.strip():
                return text, None
    except (XmlParseError, DefusedXmlException, OSError, KeyError, zipfile.BadZipFile):
        pass
    return None, "DOCX text could not be extracted. The file is stored and searchable by metadata only."


def _extract_legacy_doc(data: bytes) -> tuple[str | None, str | None]:
    if _looks_like_text(data):
        return _decode_text(data), None
    # Old .doc is an OLE binary format. This fallback extracts readable runs so
    # simple documents still become searchable without shelling out to antiword.
    sample = data.replace(b"\x00", b" ")
    words = [
        chunk.decode("latin-1", errors="ignore").strip()
        for chunk in re.findall(rb"[A-Za-z0-9][A-Za-z0-9,.;:!?@#%&()\[\]{}'\"/\-_\s]{3,}", sample)
    ]
    text = "\n".join(chunk for chunk in words if len(chunk.split()) >= 2)
    if text.strip():
        return text, None
    return None, "Legacy DOC text could not be extracted. The file is stored and searchable by metadata only."


def _extract_text(filename: str, mime_type: str, data: bytes) -> tuple[str | None, str | None]:
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".pdf" or mime_type == "application/pdf":
        text, note = _extract_pdf(data)
        if text and _contains_secret(text):
            reason = "Secret-like content was detected; only metadata was indexed for safety."
            return _metadata_text(filename, mime_type, len(data), reason), reason
        if text:
            return text, note
        return _metadata_text(filename, mime_type, len(data), note or "PDF parser could not extract text."), note
    if ext == ".docx" or mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text, note = _extract_docx(data)
        if text and _contains_secret(text):
            reason = "Secret-like content was detected; only metadata was indexed for safety."
            return _metadata_text(filename, mime_type, len(data), reason), reason
        if text:
            return text, note
        return _metadata_text(filename, mime_type, len(data), note or "DOCX parser could not extract text."), note
    if ext == ".doc" or mime_type == "application/msword":
        text, note = _extract_legacy_doc(data)
        if text and _contains_secret(text):
            reason = "Secret-like content was detected; only metadata was indexed for safety."
            return _metadata_text(filename, mime_type, len(data), reason), reason
        if text:
            return text, note
        return _metadata_text(filename, mime_type, len(data), note or "DOC parser could not extract text."), note
    if ext == ".csv" or mime_type == "text/csv":
        text = _decode_text(data)
        if _contains_secret(text):
            note = "Secret-like content was detected; only metadata was indexed for safety."
            return _metadata_text(filename, mime_type, len(data), note), note
        try:
            rows = csv.reader(io.StringIO(text))
            return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows), None
        except csv.Error:
            return text, None
    if ext in SUPPORTED_TEXT_EXTENSIONS or mime_type.startswith("text/") or _looks_like_text(data):
        text = _decode_text(data)
        if _contains_secret(text):
            note = "Secret-like content was detected; only metadata was indexed for safety."
            return _metadata_text(filename, mime_type, len(data), note), note
        return text, None
    parser_note = (
        f"{ext or 'file'} parser is not installed yet; the file is stored and searchable by metadata only."
    )
    return _metadata_text(filename, mime_type, len(data), parser_note), parser_note


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


def knowledge_overview(db: Session, principal: Principal, *, limit: int = 6) -> str | None:
    """Short metadata-only inventory for prompt context.

    This lets every model know AI Knowledge exists without dumping document
    content. Actual chunks still go through retrieve_context().
    """
    rows = list_documents(db, principal)[: max(1, min(limit, 10))]
    if not rows:
        return None
    indexed = sum(1 for r in rows if r.status == "indexed")
    metadata_only = sum(1 for r in rows if (r.meta or {}).get("metadata_only") or r.status == "uploaded")
    lines = [
        "[AI Knowledge library]",
        f"Documents visible to this workspace: {len(rows)} shown, {indexed} indexed, {metadata_only} metadata-only.",
    ]
    for row in rows:
        mode = "metadata-only" if (row.meta or {}).get("metadata_only") or row.status == "uploaded" else row.status
        lines.append(f"- {row.title} ({row.filename}) — {mode}, {row.chunk_count} chunk(s)")
    lines.append("Use retrieved chunks when available; for metadata-only files, say only that the file exists unless a parser/index is available.")
    return "\n".join(lines)


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
    limit = _knowledge_upload_limit_bytes()
    if len(data) > limit:
        mb = max(1, limit // (1024 * 1024))
        raise ValidationAppError(f"Knowledge document exceeds the {mb} MB upload limit.")

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
            meta={"filename": safe, "metadata_only": bool(error)},
        ))
    row.status = "uploaded" if error else "indexed"
    row.chunk_count = len(pieces)
    row.last_indexed_at = datetime.now(timezone.utc) if not error else None
    row.error_message = error
    row.meta = {
        "indexable": not bool(error),
        "metadata_only": bool(error),
        "upload_limit_mb": max(1, limit // (1024 * 1024)),
    }
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
    metadata_only = bool((row.meta or {}).get("metadata_only")) or any((c.meta or {}).get("metadata_only") for c in old_chunks)
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
            meta={"filename": row.filename, "reindexed": True, "metadata_only": metadata_only},
        ))
    row.status = "uploaded" if metadata_only and pieces else ("indexed" if pieces else "failed")
    row.chunk_count = len(pieces)
    row.last_indexed_at = datetime.now(timezone.utc) if pieces and not metadata_only else row.last_indexed_at
    if metadata_only and pieces:
        row.error_message = row.error_message or "Text content is not available for this file type yet."
    else:
        row.error_message = None if pieces else "No chunks were produced while re-indexing."
    row.meta = {**(row.meta or {}), "metadata_only": metadata_only, "indexable": not metadata_only}
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
            AiKnowledgeDocument.status.in_(("indexed", "uploaded")),
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
