"""Cursor-compatible provider adapter.

Cursor's public API is agent/workflow-oriented, not a generic chat-completions
API. This adapter therefore targets Cursor-compatible/OpenAI-compatible gateway
endpoints configured by the user, and requires an explicit base URL.
"""

from __future__ import annotations

from app.services.ai_providers.base import OpenAICompatibleProvider, VerifyResult


class CursorProvider(OpenAICompatibleProvider):
    id = "cursor"
    name = "Cursor AI Agent"
    external = True
    requires_api_key = True
    default_base_url = ""
    default_model = ""
    supports_tools = True

    def is_configured(self, public: dict, secrets: dict) -> bool:
        return bool(secrets.get("api_key") and public.get("base_url"))

    def test_connection(self, public: dict, secrets: dict) -> VerifyResult:
        if not secrets.get("api_key"):
            return VerifyResult("not_configured", "API key not set")
        if not public.get("base_url"):
            return VerifyResult(
                "not_configured",
                "Base URL not set. Cursor AI in AllHaven needs a Cursor/OpenAI-compatible gateway URL.",
            )
        return super().test_connection(public, secrets)
