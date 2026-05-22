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


# Marker used to flag an infrastructure/proxy block (e.g. an egress allowlist),
# so it is reported honestly as "unavailable / blocked by network" instead of
# being mistaken for a provider auth rejection.
NETWORK_BLOCK_MARKER = "NETWORK_POLICY_BLOCK"
_NETWORK_BLOCK_SIGNATURES = (
    "not in allowlist",
    "allowlist",
    "forbidden host",
    "proxy",
    "gateway",
    "tunnel",
    "egress",
)


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
        # An infrastructure/proxy block (egress allowlist, gateway) is NOT a
        # provider auth failure. Detect the plain-text signature and surface it as
        # an error so callers report it honestly as "unavailable", not "key rejected".
        if body is None and resp.status_code in (403, 407, 451, 502, 503):
            text = (resp.text or "")[:200]
            low = text.lower()
            if any(sig in low for sig in _NETWORK_BLOCK_SIGNATURES):
                return resp.status_code, None, f"{NETWORK_BLOCK_MARKER}: {text.strip()}"
        return resp.status_code, body, ""
    except Exception as exc:  # noqa: BLE001 - network failures are expected/honest
        return None, None, str(exc)[:200]


def interpret_http(code: Optional[int], err: str) -> VerifyResult:
    """Map an HTTP result to an honest verification status.

    * blocked by network policy/proxy   -> unavailable (NOT "key rejected")
    * no response (exception/timeout)    -> unavailable
    * 200/2xx                            -> online
    * 401/403                            -> error (invalid/unauthorized key)
    * other 4xx/5xx                      -> error
    """
    if err and NETWORK_BLOCK_MARKER in err:
        return VerifyResult(
            "unavailable",
            "Blocked by the network policy (host not allowed) — this server can't reach "
            "the provider. Run AllHaven where the host is reachable, or allow it in your "
            "environment's network policy.",
        )
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


def network_error_message(err: str) -> str:
    """Friendly message for a transport-level failure (no HTTP response)."""
    low = (err or "").lower()
    if NETWORK_BLOCK_MARKER.lower() in low or "not in allowlist" in low:
        return (
            "could not reach the provider — the host is blocked by the current network policy "
            "(egress allowlist). This is a network restriction, not your API key. Run AllHaven "
            "where the host is reachable (e.g. your own machine), or allow the host in your "
            "environment's network policy."
        )
    if "name resolution" in low or "getaddrinfo" in low or "nodename" in low:
        return (
            "could not reach the provider — DNS/name resolution failed. Check your internet "
            "connection (or proxy/firewall), or use local Ollama which needs no internet."
        )
    if "timed out" in low or "timeout" in low:
        return "could not reach the provider — the request timed out. Try again or check your network."
    if "connection refused" in low or "refused" in low:
        return "could not reach the provider — connection refused. Is the URL correct and the service running?"
    return f"could not reach the provider (network error): {err}"


def chat_error_message(code: Optional[int], body: Optional[dict]) -> str:
    """Human-friendly explanation for a failed chat call."""
    # Prefer the provider's own message when available.
    detail = ""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            detail = str(err.get("message") or "")
        elif isinstance(err, str):
            detail = err
    suffix = f" — {detail}" if detail else ""
    if code in (401, 403):
        return f"the API key was rejected (HTTP {code}). Check the key in Settings.{suffix}"
    if code == 402:
        return (
            "the provider requires credits/payment (HTTP 402). Add credits on the provider, "
            "switch the default model to a free one, choose another provider, or use local "
            f"Ollama (free).{suffix}"
        )
    if code == 404:
        return f"the model or endpoint was not found (HTTP 404). Check the model name.{suffix}"
    if code == 429:
        return f"the provider rate-limited the request (HTTP 429). Try again shortly.{suffix}"
    if code and code >= 500:
        return f"the provider had a server error (HTTP {code}). Try again later.{suffix}"
    return f"the request failed (HTTP {code}).{suffix}"


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
            return ChatResult(False, error=network_error_message(err))
        if code == 200 and body:
            try:
                return ChatResult(True, content=body["choices"][0]["message"]["content"])
            except (KeyError, IndexError, TypeError):
                return ChatResult(False, error="the provider returned an unexpected response")
        return ChatResult(False, error=chat_error_message(code, body))
