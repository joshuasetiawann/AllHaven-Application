"""Drive file schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.schemas.common import ORMModel


class DriveFileOut(ORMModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    updated_at: datetime
