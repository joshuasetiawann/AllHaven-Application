"""AI provider config request schemas."""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator

PRIVACY_MODES = ("local_private", "external_allowed", "manual_provider")


class AiProviderUpdateRequest(BaseModel):
    public_config: Dict[str, str] = Field(default_factory=dict)
    secrets: Dict[str, str] = Field(default_factory=dict)
    default_model: Optional[str] = None
    privacy_mode: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    enabled: Optional[bool] = None

    @field_validator("privacy_mode")
    @classmethod
    def _privacy(cls, v):
        if v is not None and v not in PRIVACY_MODES:
            raise ValueError(f"privacy_mode must be one of {PRIVACY_MODES}")
        return v
