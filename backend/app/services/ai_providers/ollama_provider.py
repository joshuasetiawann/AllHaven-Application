"""Ollama local provider adapter (no API key; local-first)."""

from __future__ import annotations

from typing import Optional

from app.services.ai_providers.base import (
    AIProvider,
    ChatResult,
    VerifyResult,
    chat_error_message,
    interpret_http,
    network_error_message,
    safe_request,
)

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(AIProvider):
    id = "ollama"
    name = "Ollama Local Agent"
    external = False
    requires_api_key = False
    default_model = "llama3.1"

    def base_url(self, public: dict) -> str:
        return (public.get("base_url") or DEFAULT_BASE_URL).rstrip("/")

    def is_configured(self, public: dict, secrets: dict) -> bool:
        return bool(public.get("base_url"))

    def test_connection(self, public: dict, secrets: dict) -> VerifyResult:
        if not public.get("base_url"):
            return VerifyResult("not_configured", "Base URL not set")
        # GET /api/tags lists local models; connection refused -> unavailable.
        code, _, err = safe_request("GET", f"{self.base_url(public)}/api/tags", timeout=5.0)
        return interpret_http(code, err)

    def chat(
        self, public: dict, secrets: dict, messages: list[dict],
        model: Optional[str] = None, params: Optional[dict] = None,
    ) -> ChatResult:
        if not public.get("base_url"):
            return ChatResult(False, error="Base URL not set")
        chosen = model or public.get("default_model") or self.default_model
        body_json = {"model": chosen, "messages": messages, "stream": False}
        # Ollama takes sampling settings under "options".
        options = {k: params[k] for k in ("temperature", "top_p") if params and params.get(k) is not None}
        if options:
            body_json["options"] = options
        code, body, err = safe_request(
            "POST",
            f"{self.base_url(public)}/api/chat",
            json=body_json,
            timeout=30.0,
        )
        if err:
            return ChatResult(False, error=network_error_message(err))
        if code == 200 and body:
            try:
                return ChatResult(True, content=body["message"]["content"])
            except (KeyError, TypeError):
                return ChatResult(False, error="the provider returned an unexpected response")
        return ChatResult(False, error=chat_error_message(code, body))
