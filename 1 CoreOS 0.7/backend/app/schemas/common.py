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
    if not _EMAIL_RE.match(value):
        raise ValueError("Invalid email address")
    return value
