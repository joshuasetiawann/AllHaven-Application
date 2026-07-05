"""Integration and AI-agent configuration models.

Both tables store per-workspace configuration with a shared shape:
    * ``public_config``    — non-secret values (base URLs, model names, …)
    * ``encrypted_secrets``— secret values, encrypted at rest (never returned raw)
    * ``status``           — not_configured | configured | online | error | disabled
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

INTEGRATION_STATUSES = ("not_configured", "configured", "online", "error", "disabled")


class IntegrationConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Config + encrypted secrets for a tool/infrastructure integration."""

    __tablename__ = "integration_configs"
    __table_args__ = (UniqueConstraint("workspace_id", "provider_id", name="uq_integration_workspace_provider"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="not_configured", nullable=False)
    public_config: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    encrypted_secrets: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AiAgentConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Config + encrypted secrets + preferences for an AI provider/agent."""

    __tablename__ = "ai_agent_configs"
    __table_args__ = (UniqueConstraint("workspace_id", "provider_id", name="uq_ai_agent_workspace_provider"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(50), default="ai_provider", nullable=False)
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)

    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="not_configured", nullable=False)
    default_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    privacy_mode: Mapped[str] = mapped_column(String(30), default="local_private", nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)

    public_config: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    encrypted_secrets: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
