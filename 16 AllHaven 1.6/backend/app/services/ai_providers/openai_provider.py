"""OpenAI (and OpenAI-compatible) provider adapter."""

from __future__ import annotations

from app.services.ai_providers.base import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    id = "openai"
    name = "OpenAI Agent"
    external = True
    requires_api_key = True
    default_base_url = "https://api.openai.com/v1"
    default_model = "gpt-4.1-mini"
    supports_image = True
    supports_tools = True
