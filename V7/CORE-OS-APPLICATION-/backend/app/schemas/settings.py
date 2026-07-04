"""Settings / integration status schemas."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel


class IntegrationStatus(BaseModel):
    key: str
    name: str
    # One of: connected | configured | not_configured | error
    status: str
    configured: bool
    detail: str


class IntegrationsOut(BaseModel):
    integrations: List[IntegrationStatus]
