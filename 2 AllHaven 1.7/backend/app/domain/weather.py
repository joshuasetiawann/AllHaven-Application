"""Saved weather locations (workspace-scoped, MVP).

Saved/default locations persist here. The weather API key + provider live in the
``weather_api`` integration config; current weather is only returned from a real
provider response (never faked).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class WeatherLocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "weather_locations"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
