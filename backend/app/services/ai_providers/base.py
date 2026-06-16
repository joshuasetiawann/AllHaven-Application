"""Base classes and helpers for AI provider adapters.

Verification is honest: a provider is only "online" after a real, authenticated
check succeeds. Endpoints that don't actually validate the key (e.g. a public
``/models`` list) must NOT be used for verification — see per-provider overrides.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

DEFAULT_TIMEOUT = 8.0

# Verification statuses produced by test_connection.
VERIFY_STATUSES = ("online", "error", "unavailable", "not_configured", "configured")


@dataclass
class ChatResult:
    ok: bool
    content: str = ""
    error: str = ""


@dataclass
class VerifyResult:
    """Typed result of a connection test. ``status`` is one of VERIFY_STATUSES."""

    status: str
    message: str = ""


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


def interpret_http(code: Optional[int], err: str) -> VerifyResult:
    """Map an HTTP result to an honest verification status.

    * no response (exception/timeout) -> unavailable
    * 200/2xx                          -> online
    * 401/403                          -> error (invalid/unauthorized key)
    * other 4xx/5xx                    -> error
    """
    if err or code is None:
        return VerifyResult("unavailable", f"Could not reach provider: {err}" if err else "No response")
    if 200 <= code < 300:
        return VerifyResult("online", "Verified")
    if code in (401, 403):
        return VerifyResult("error", "Unauthorized — the API key was rejected")
    if code == 404:
        return VerifyResult("error", "Verification endpoint not found (check base URL / model)")
    if code == 429:
        return VerifyResult("error", "Rate limited by provider")
    if code >= 500:
        return VerifyResult("error", f"Provider error (HTTP {code})")
    return VerifyResult("error", f"Verification failed (HTTP {code})")


class AIProvider:
    """Provider adapter interface."""

    id: str = ""
    name: str = ""
    external: bool = True
    requires_api_key: bool = True
    default_model: str = ""

    def is_configured(self, public: dict, secrets: dict) -> bool:
        raise NotImplementedError

    def test_connection(self, public: dict, secrets: dict) -> VerifyResult:
        raise NotImplementedError

    def chat(self, public: dict, secrets: dict, messages: list[dict], model: Optional[str] = None) -> ChatResult:
        raise NotImplementedError


class OpenAICompatibleProvider(AIProvider):
    """Shared adapter for OpenAI-style /chat/completions + /models endpoints.

    ``verify_path`` MUST be an authenticated endpoint so a bad key fails. If a
    provider's ``/models`` is public, override ``test_connection`` (see OpenRouter).
    """

    default_base_url = "https://api.openai.com/v1"
    extra_headers: dict = {}
    verify_path = "/models"

    def base_url(self, public: dict) -> str:
        return (public.get("base_url") or self.default_base_url).rstrip("/")

    def _headers(self, key: str) -> dict:
        return {"Authorization": f"Bearer {key}", **self.extra_headers}

    def is_configured(self, public: dict, secrets: dict) -> bool:
        return bool(secrets.get("api_key"))

    def test_connection(self, public: dict, secrets: dict) -> VerifyResult:
        key = secrets.get("api_key")
        if not key:
            return VerifyResult("not_configured", "API key not set")
        code, _, err = safe_request(
            "GET", f"{self.base_url(public)}{self.verify_path}", headers=self._headers(key)
        )
        return interpret_http(code, err)

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
