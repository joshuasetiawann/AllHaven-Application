"""AI Knowledge documents and searchable chunks.

Drive stores arbitrary files. AI Knowledge stores user-approved documents that
are parsed into text chunks and may be retrieved into AI chat context.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

KNOWLEDGE_STATUSES = ("uploaded", "indexing", "indexed", "failed")


class AiKnowledgeDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_knowledge_documents"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "id", name="uq_ai_knowledge_documents_workspace_id_id"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "source_drive_file_id"],
            ["drive_files.workspace_id", "drive_files.id"],
            name="fk_ai_knowledge_documents_workspace_source_drive_file__eab5de47",
            ondelete="NO ACTION",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False, default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded", index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_drive_file_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("drive_files.id", ondelete="SET NULL"), nullable=True
    )
    meta: Mapped[dict | None] = mapped_column("metadata", JSONType, nullable=True)


class AiKnowledgeChunk(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_knowledge_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "document_id"],
            ["ai_knowledge_documents.workspace_id", "ai_knowledge_documents.id"],
            name="fk_ai_knowledge_chunks_workspace_document_id_ai_knowle_b85369ac",
            ondelete="CASCADE",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("ai_knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
