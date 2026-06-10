"""Blackbox AI provider adapter (OpenAI-compatible API)."""

from __future__ import annotations

from app.services.ai_providers.base import OpenAICompatibleProvider


class BlackboxProvider(OpenAICompatibleProvider):
    id = "blackbox"
    name = "Blackbox Agent"
    external = True
    requires_api_key = True
    default_base_url = "https://api.blackbox.ai/v1"
    default_model = "blackbox-default"
