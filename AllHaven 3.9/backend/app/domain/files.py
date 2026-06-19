"""Drive file metadata (workspace-scoped, local storage MVP).

File bytes live under a local storage directory (never in the frontend); this
table stores metadata only. Path traversal is prevented in the service layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class DriveFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "drive_files"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False, default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Path relative to the configured storage root (never an absolute/escaping path).
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
