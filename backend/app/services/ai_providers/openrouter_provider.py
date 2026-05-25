"""OpenRouter provider adapter (OpenAI-compatible API)."""

from __future__ import annotations

from app.services.ai_providers.base import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    id = "openrouter"
    name = "OpenRouter Agent"
    external = True
    requires_api_key = True
    default_base_url = "https://openrouter.ai/api/v1"
    default_model = "openai/gpt-4.1-mini"
    extra_headers = {"HTTP-Referer": "https://coreos.local", "X-Title": "CoreOS Command Center"}
