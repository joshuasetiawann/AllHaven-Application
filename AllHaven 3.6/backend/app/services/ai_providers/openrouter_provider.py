"""OpenRouter provider adapter (OpenAI-compatible API).

NOTE: OpenRouter's ``/models`` endpoint is PUBLIC (no auth), so it cannot verify
a key — a random key would return 200. Verification uses the authenticated
``/key`` endpoint instead, which returns 401 for an invalid key.
"""

from __future__ import annotations

from app.services.ai_providers.base import OpenAICompatibleProvider, VerifyResult, interpret_http, safe_request


class OpenRouterProvider(OpenAICompatibleProvider):
    id = "openrouter"
    name = "OpenRouter Agent"
    external = True
    requires_api_key = True
    default_base_url = "https://openrouter.ai/api/v1"
    default_model = "openai/gpt-4.1-mini"
    supports_image = True
    supports_tools = True
    extra_headers = {"HTTP-Referer": "https://allhaven.local", "X-Title": "AllHaven Command Center"}

    def test_connection(self, public: dict, secrets: dict) -> VerifyResult:
        key = secrets.get("api_key")
        if not key:
            return VerifyResult("not_configured", "API key not set")
        # /key requires authentication, so an invalid key correctly returns 401.
        code, _, err = safe_request("GET", f"{self.base_url(public)}/key", headers=self._headers(key))
        return interpret_http(code, err)
