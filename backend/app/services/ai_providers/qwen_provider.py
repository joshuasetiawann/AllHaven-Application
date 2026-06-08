"""Qwen / DashScope provider adapter (OpenAI-compatible API)."""

from __future__ import annotations

from app.services.ai_providers.base import OpenAICompatibleProvider


class QwenProvider(OpenAICompatibleProvider):
    id = "qwen"
    name = "Qwen Agent"
    external = True
    requires_api_key = True
    default_base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    default_model = "qwen-plus"
    supports_tools = True
