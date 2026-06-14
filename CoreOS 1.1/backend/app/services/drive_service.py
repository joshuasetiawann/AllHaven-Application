"""Drive file storage (local filesystem MVP, workspace-scoped).

Security:
    * Bytes are stored under a per-workspace folder inside the storage root.
    * The stored name is ``<uuid>_<sanitized-basename>`` — the client filename is
      reduced to its basename, so path traversal (``../``, absolute paths) cannot
      escape the storage root. Every resolved path is asserted to stay inside it.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.principal import Principal
from app.domain.files import DriveFile

MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB MVP cap


def _storage_root() -> Path:
    root = Path(settings.drive_storage_path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_basename(filename: str) -> str:
    # Reduce to a basename and strip any path separators / traversal segments.
    base = os.path.basename((filename or "").replace("\\", "/")).strip()
    base = base.replace("..", "").strip(". ")
    return base or "file"


def list_files(db: Session, principal: Principal) -> List[DriveFile]:
    stmt = (
        select(DriveFile)
        .where(DriveFile.workspace_id == principal.workspace_id, DriveFile.is_deleted.is_(False))
        .order_by(DriveFile.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def _get(db: Session, principal: Principal, file_id: uuid.UUID) -> DriveFile:
    row = db.scalar(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.workspace_id == principal.workspace_id,
            DriveFile.is_deleted.is_(False),
        )
    )
    if not row:
        raise NotFoundError("File not found.")
    return row


def save_file(db: Session, principal: Principal, *, filename: str, content_type: str, data: bytes) -> DriveFile:
    if not data:
        raise ValidationAppError("Uploaded file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise ValidationAppError("File exceeds the 25 MB limit.")

    root = _storage_root()
    ws_dir = (root / str(principal.workspace_id)).resolve()
    # Defense in depth: the workspace dir must remain inside the storage root.
    if os.path.commonpath([str(root), str(ws_dir)]) != str(root):
        raise ValidationAppError("Invalid storage path.")
    ws_dir.mkdir(parents=True, exist_ok=True)

    safe = _safe_basename(filename)
    stored_name = f"{uuid.uuid4().hex}_{safe}"
    dest = (ws_dir / stored_name).resolve()
    if os.path.commonpath([str(root), str(dest)]) != str(root):
        raise ValidationAppError("Invalid storage path.")
    dest.write_bytes(data)

    rel = os.path.relpath(str(dest), str(root))
    row = DriveFile(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        filename=safe,
        content_type=content_type or "application/octet-stream",
        size_bytes=len(data),
        storage_path=rel,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def resolve_path(db: Session, principal: Principal, file_id: uuid.UUID) -> tuple[DriveFile, str]:
    """Return (row, absolute_path) for download, asserting the path is in-root."""
    row = _get(db, principal, file_id)
    root = _storage_root()
    abs_path = (root / row.storage_path).resolve()
    if os.path.commonpath([str(root), str(abs_path)]) != str(root) or not abs_path.exists():
        raise NotFoundError("Stored file is missing.")
    return row, str(abs_path)


def delete_file(db: Session, principal: Principal, file_id: uuid.UUID) -> None:
    row = _get(db, principal, file_id)
    row.is_deleted = True
    db.commit()
    # Best-effort removal of bytes; metadata is already soft-deleted.
    try:
        root = _storage_root()
        abs_path = (root / row.storage_path).resolve()
        if os.path.commonpath([str(root), str(abs_path)]) == str(root) and abs_path.exists():
            abs_path.unlink()
    except Exception:  # noqa: BLE001 - bytes cleanup is best-effort
        pass
