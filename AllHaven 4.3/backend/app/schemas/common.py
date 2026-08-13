"""Shared schema helpers."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ORMModel(BaseModel):
    """Base for response models read from ORM objects."""

    model_config = ConfigDict(from_attributes=True)


def normalize_email(value: str) -> str:
    """Lowercase, trim, and validate a basic email shape."""
    value = (value or "").strip().lower()
    # Keep the API boundary aligned with the VARCHAR(320) identity columns.
    # SQLite does not enforce VARCHAR lengths, so the application must.
    if len(value) > 320:
        raise ValueError("Email address must be at most 320 characters")
    if not _EMAIL_RE.match(value):
        raise ValueError("Invalid email address")
    return value
