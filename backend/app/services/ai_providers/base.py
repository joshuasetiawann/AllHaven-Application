"""Base classes and helpers for AI provider adapters.

Adapters perform real HTTP calls so they genuinely work once a user supplies a
key. When something is missing or fails, they return an honest error — they never
fabricate success.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

DEFAULT_TIMEOUT = 8.0


@dataclass
class ChatResult:
    ok: bool
    content: str = ""
    error: str = ""


def safe_request(
    method: str,
    url: str,
    *,
    headers: Optional[dict] = None,
    json: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[Optional[int], Optional[dict], str]:
    """Perform an HTTP request, returning (status_code, json_body, error)."""
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.request(method, url, headers=headers, json=json, params=params)
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001 - body may not be JSON
            body = None
        return resp.status_code, body, ""
    except Exception as exc:  # noqa: BLE001 - network failures are expected/honest
        return None, None, str(exc)[:200]


class AIProvider:
    """Provider adapter interface."""

    id: str = ""
    name: str = ""
    external: bool = True
    requires_api_key: bool = True
    default_model: str = ""

    def is_configured(self, public: dict, secrets: dict) -> bool:
        raise NotImplementedError

    def test_connection(self, public: dict, secrets: dict) -> tuple[bool, str]:
        raise NotImplementedError

    def chat(self, public: dict, secrets: dict, messages: list[dict], model: Optional[str] = None) -> ChatResult:
        raise NotImplementedError


class OpenAICompatibleProvider(AIProvider):
    """Shared adapter for OpenAI-style /chat/completions + /models endpoints."""

    default_base_url = "https://api.openai.com/v1"
    extra_headers: dict = {}

    def base_url(self, public: dict) -> str:
        return (public.get("base_url") or self.default_base_url).rstrip("/")

    def _headers(self, key: str) -> dict:
        return {"Authorization": f"Bearer {key}", **self.extra_headers}

    def is_configured(self, public: dict, secrets: dict) -> bool:
        return bool(secrets.get("api_key"))

    def test_connection(self, public: dict, secrets: dict) -> tuple[bool, str]:
        key = secrets.get("api_key")
        if not key:
            return False, "API key not set"
        code, _, err = safe_request("GET", f"{self.base_url(public)}/models", headers=self._headers(key))
        if err:
            return False, err
        if code == 200:
            return True, ""
        return False, f"Verification failed (HTTP {code})"

    def chat(self, public: dict, secrets: dict, messages: list[dict], model: Optional[str] = None) -> ChatResult:
        key = secrets.get("api_key")
        if not key:
            return ChatResult(False, error="API key not set")
        chosen = model or public.get("default_model") or self.default_model
        code, body, err = safe_request(
            "POST",
            f"{self.base_url(public)}/chat/completions",
            headers=self._headers(key),
            json={"model": chosen, "messages": messages},
        )
        if err:
            return ChatResult(False, error=err)
        if code == 200 and body:
            try:
                return ChatResult(True, content=body["choices"][0]["message"]["content"])
            except (KeyError, IndexError, TypeError):
                return ChatResult(False, error="Unexpected response from provider")
        return ChatResult(False, error=f"Provider returned HTTP {code}")
