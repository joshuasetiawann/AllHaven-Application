"""Integration config request schemas (responses are rich dicts from the service)."""

from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, Field


class IntegrationUpdateRequest(BaseModel):
    """Public (non-secret) values and secret values to save.

    Only provided fields are updated. An explicit empty string clears a field.
    Secrets are encrypted server-side and never returned.
    """

    public_config: Dict[str, str] = Field(default_factory=dict)
    secrets: Dict[str, str] = Field(default_factory=dict)
