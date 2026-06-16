"""Anthropic (Claude) provider adapter."""

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

API_BASE = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(AIProvider):
    id = "anthropic"
    name = "Claude Agent"
    external = True
    requires_api_key = True
    default_model = "claude-sonnet-4-5"

    def _headers(self, key: str) -> dict:
        return {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}

    def is_configured(self, public: dict, secrets: dict) -> bool:
        return bool(secrets.get("api_key"))

    def test_connection(self, public: dict, secrets: dict) -> VerifyResult:
        key = secrets.get("api_key")
        if not key:
            return VerifyResult("not_configured", "API key not set")
        # /models requires the x-api-key header; an invalid key returns 401.
        code, _, err = safe_request("GET", f"{API_BASE}/models", headers=self._headers(key))
        return interpret_http(code, err)

    def chat(
        self, public: dict, secrets: dict, messages: list[dict],
        model: Optional[str] = None, params: Optional[dict] = None,
    ) -> ChatResult:
        key = secrets.get("api_key")
        if not key:
            return ChatResult(False, error="API key not set")
        chosen = model or public.get("default_model") or self.default_model
        # Anthropic uses a top-level system param + user/assistant messages.
        system = next((m["content"] for m in messages if m.get("role") == "system"), None)
        convo: list[dict] = []
        for m in messages:
            role = m.get("role")
            if role not in ("user", "assistant"):
                continue
            imgs = m.get("images") or []
            if imgs and role == "user":
                blocks: list[dict] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for u in imgs:
                    media, b64 = parse_data_url(u)
                    blocks.append({"type": "image", "source": {"type": "base64", "media_type": media or "image/png", "data": b64}})
                convo.append({"role": "user", "content": blocks})
            else:
                convo.append({"role": role, "content": m.get("content") or ""})
        payload: dict = {"model": chosen, "max_tokens": (params or {}).get("max_tokens") or 1024, "messages": convo}
        for k in ("temperature", "top_p"):
            if params and params.get(k) is not None:
                payload[k] = params[k]
        if system:
            payload["system"] = system
        code, body, err = safe_request(
            "POST", f"{API_BASE}/messages", headers=self._headers(key), json=payload
        )
        if err:
            return ChatResult(False, error=network_error_message(err))
        if code == 200 and body:
            try:
                return ChatResult(True, content=body["content"][0]["text"])
            except (KeyError, IndexError, TypeError):
                return ChatResult(False, error="the provider returned an unexpected response")
        return ChatResult(False, error=chat_error_message(code, body))
