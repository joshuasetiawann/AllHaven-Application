"""DeepSeek provider adapter (OpenAI-compatible API)."""

from __future__ import annotations

from app.services.ai_providers.base import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    id = "deepseek"
    name = "DeepSeek Agent"
    external = True
    requires_api_key = True
    default_base_url = "https://api.deepseek.com/v1"
    default_model = "deepseek-chat"
    supports_tools = True
