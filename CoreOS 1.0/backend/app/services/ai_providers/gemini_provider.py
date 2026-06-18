"""Google Gemini provider adapter."""

from __future__ import annotations

from typing import Optional

from app.services.ai_providers.base import (
    AIProvider,
    ChatResult,
    VerifyResult,
    chat_error_message,
    interpret_http,
    safe_request,
)

API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(AIProvider):
    id = "gemini"
    name = "Gemini Agent"
    external = True
    requires_api_key = True
    default_model = "gemini-1.5-flash"

    def is_configured(self, public: dict, secrets: dict) -> bool:
        return bool(secrets.get("api_key"))

    def test_connection(self, public: dict, secrets: dict) -> VerifyResult:
        key = secrets.get("api_key")
        if not key:
            return VerifyResult("not_configured", "API key not set")
        # The key is validated server-side; an invalid key returns 400/403.
        code, _, err = safe_request("GET", f"{API_BASE}/models", params={"key": key})
        return interpret_http(code, err)

    def chat(self, public: dict, secrets: dict, messages: list[dict], model: Optional[str] = None) -> ChatResult:
        key = secrets.get("api_key")
        if not key:
            return ChatResult(False, error="API key not set")
        chosen = model or public.get("default_model") or self.default_model
        contents = [
            {"role": "user" if m.get("role") != "assistant" else "model", "parts": [{"text": m.get("content", "")}]}
            for m in messages
            if m.get("role") in ("user", "assistant")
        ]
        code, body, err = safe_request(
            "POST",
            f"{API_BASE}/models/{chosen}:generateContent",
            params={"key": key},
            json={"contents": contents},
        )
        if err:
            return ChatResult(False, error=network_error_message(err))
        if code == 200 and body:
            try:
                return ChatResult(True, content=body["candidates"][0]["content"]["parts"][0]["text"])
            except (KeyError, IndexError, TypeError):
                return ChatResult(False, error="the provider returned an unexpected response")
        return ChatResult(False, error=chat_error_message(code, body))
