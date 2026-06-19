"""Grok / xAI provider adapter (OpenAI-compatible API)."""

from __future__ import annotations

from app.services.ai_providers.base import OpenAICompatibleProvider


class GrokProvider(OpenAICompatibleProvider):
    id = "grok"
    name = "Grok / xAI Agent"
    external = True
    requires_api_key = True
    default_base_url = "https://api.x.ai/v1"
    default_model = "grok-2-latest"
    supports_image = True
    supports_tools = True
