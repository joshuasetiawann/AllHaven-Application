"""Local automation definitions (workspace-scoped, MVP).

Definitions persist but are never executed by AllHaven in the MVP — they are
disabled-safe drafts. n8n connection status is reported honestly via Settings.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin


class Automation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "automations"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(60), nullable=False, default="manual")
    action_type: Mapped[str] = mapped_column(String(60), nullable=False, default="noop")
    config: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    # Definitions are created disabled-safe; AllHaven does not execute them.
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
