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
    parse_data_url,
    safe_request,
)

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(AIProvider):
    id = "ollama"
    name = "Ollama Local Agent"
    external = False
    requires_api_key = False
    default_model = "llama3.1"
    supports_image = True  # vision models such as llava

    def _resolved(self, public: dict):
        """(url, mode, reason) for the selected connection mode — explicit URL only."""
        from app.services.connection_resolver import resolve

        return resolve(public)

    def base_url(self, public: dict) -> str:
        """Endpoint used for CHAT. Honors the bridge mode; falls back to localhost only
        for local/auto (the backend's own machine) — never for a tailscale mode with no
        URL. (Chat is only reached when is_configured, so the localhost fallback is safe.)"""
        url, mode, _reason = self._resolved(public)
        if url:
            return url.rstrip("/")
        return DEFAULT_BASE_URL.rstrip("/") if mode in ("local_desktop", "auto") else ""

    def is_configured(self, public: dict, secrets: dict) -> bool:
        # Configured only when a URL is EXPLICITLY set for the mode (not the implicit
        # localhost default), so "not configured" status stays honest.
        return bool(self._resolved(public)[0])

    def test_connection(self, public: dict, secrets: dict) -> VerifyResult:
        url, _mode, reason = self._resolved(public)
        if not url:
            return VerifyResult("not_configured", reason or "Base URL not set")
        # GET /api/tags lists local models; connection refused -> unavailable.
        code, _, err = safe_request("GET", f"{url.rstrip('/')}/api/tags", timeout=5.0)
        return interpret_http(code, err)

    def chat(
        self, public: dict, secrets: dict, messages: list[dict],
        model: Optional[str] = None, params: Optional[dict] = None,
    ) -> ChatResult:
        base = self.base_url(public)
        if not base:
            # Honest unavailable — no fake response when the bridge endpoint is unset.
            return ChatResult(False, error="Ollama is not reachable for the selected connection mode. Configure the Desktop Bridge in Settings.")
        chosen = model or public.get("default_model") or self.default_model
        # Ollama carries images as base64 strings under each message's "images".
        out_messages = []
        for m in messages:
            msg = {"role": m.get("role", "user"), "content": m.get("content") or ""}
            imgs = m.get("images") or []
            if imgs:
                msg["images"] = [parse_data_url(u)[1] for u in imgs]
            out_messages.append(msg)
        body_json = {"model": chosen, "messages": out_messages, "stream": False}
        # Ollama takes sampling settings under "options".
        options = {k: params[k] for k in ("temperature", "top_p") if params and params.get(k) is not None}
        if options:
            body_json["options"] = options
        code, body, err = safe_request(
            "POST",
            f"{base}/api/chat",
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
