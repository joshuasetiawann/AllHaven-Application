"""Base classes and helpers for AI provider adapters.

Verification is honest: a provider is only "online" after a real, authenticated
check succeeds. Endpoints that don't actually validate the key (e.g. a public
``/models`` list) must NOT be used for verification — see per-provider overrides.
"""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.core.config import settings

DEFAULT_TIMEOUT = 8.0

# Verification statuses produced by test_connection.
VERIFY_STATUSES = ("online", "error", "unavailable", "not_configured", "configured")


@dataclass
class ChatResult:
    ok: bool
    content: str = ""
    error: str = ""
    # Native tool/function calls requested by the model, normalized to
    # [{"id": str, "name": str, "arguments": str(JSON)}]. None for plain replies.
    tool_calls: Optional[list] = None


# Generation parameters (temperature, top_p, penalties, max_tokens) the Reasoning
# Quality Layer passes per call. Adapters forward the subset their API supports.
_OPENAI_PARAM_KEYS = ("temperature", "top_p", "presence_penalty", "frequency_penalty", "max_tokens")


def openai_gen_params(params: Optional[dict]) -> dict:
    """Whitelist of OpenAI-style generation params, dropping unset values."""
    if not params:
        return {}
    return {k: params[k] for k in _OPENAI_PARAM_KEYS if params.get(k) is not None}


def parse_data_url(url: str) -> tuple[str, str]:
    """Return (media_type, base64_data) from a data URL; ('', url) otherwise."""
    if isinstance(url, str) and url.startswith("data:") and "," in url:
        head, b64 = url.split(",", 1)
        media = head[5:].split(";")[0] or "image/png"
        return media, b64
    return "", url


def openai_message_content(message: dict):
    """OpenAI chat 'content': a plain string, or a parts array when images attach.

    A message may carry ``images`` (a list of data URLs). Vision-capable models
    (e.g. gpt-4o) accept image_url parts; non-vision models simply ignore/err.
    """
    images = message.get("images") or []
    text = message.get("content") or ""
    if not images:
        return text
    parts: list[dict] = [{"type": "text", "text": text}] if text else []
    for img in images:
        parts.append({"type": "image_url", "image_url": {"url": img}})
    return parts


@dataclass
class VerifyResult:
    """Typed result of a connection test. ``status`` is one of VERIFY_STATUSES."""

    status: str
    message: str = ""


# Marker used to flag an infrastructure/proxy block (e.g. an egress allowlist),
# so it is reported honestly as "unavailable / blocked by network" instead of
# being mistaken for a provider auth rejection.
NETWORK_BLOCK_MARKER = "NETWORK_POLICY_BLOCK"
_TAILSCALE_SHARED_NET = ipaddress.ip_network("100.64.0.0/10")
_NETWORK_BLOCK_SIGNATURES = (
    "not in allowlist",
    "allowlist",
    "forbidden host",
    "proxy",
    "gateway",
    "tunnel",
    "egress",
)


def _blocked_private_ip(value) -> bool:
    return (
        value.is_loopback
        or value.is_private
        or value.is_link_local
        or value.is_multicast
        or value.is_reserved
        or value.is_unspecified
        or value in _TAILSCALE_SHARED_NET
    )


def _network_policy_error(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"{NETWORK_BLOCK_MARKER}: unsupported URL scheme"
    host = parsed.hostname
    if not host:
        return f"{NETWORK_BLOCK_MARKER}: missing URL host"
    if settings.integration_private_urls_allowed:
        return ""

    addresses = set()
    try:
        addresses.add(ipaddress.ip_address(host))
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            addresses.update(ipaddress.ip_address(info[4][0]) for info in infos)
        except (OSError, ValueError):
            return ""

    if any(_blocked_private_ip(addr) for addr in addresses):
        return f"{NETWORK_BLOCK_MARKER}: private integration URLs are disabled for this deployment"
    return ""


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
    policy_error = _network_policy_error(url)
    if policy_error:
        return None, None, policy_error
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
    # Capability metadata (honest defaults). Vision/tools are off unless a concrete
    # adapter opts in. Used to route images only to vision-capable providers.
    supports_text: bool = True
    supports_image: bool = False
    supports_tools: bool = False

    def capabilities(self) -> dict:
        return {"text": self.supports_text, "image": self.supports_image, "tools": self.supports_tools}

    def is_configured(self, public: dict, secrets: dict) -> bool:
        raise NotImplementedError

    def test_connection(self, public: dict, secrets: dict) -> VerifyResult:
        raise NotImplementedError

    def chat(
        self, public: dict, secrets: dict, messages: list[dict],
        model: Optional[str] = None, params: Optional[dict] = None,
    ) -> ChatResult:
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

    def chat(
        self, public: dict, secrets: dict, messages: list[dict],
        model: Optional[str] = None, params: Optional[dict] = None,
        tools: Optional[list] = None,
    ) -> ChatResult:
        key = secrets.get("api_key")
        if not key:
            return ChatResult(False, error="API key not set")
        chosen = model or public.get("default_model") or self.default_model
        payload_messages = []
        for m in messages:
            pm: dict = {"role": m.get("role", "user"), "content": openai_message_content(m)}
            # Tool-call plumbing (assistant tool_calls echo + tool results).
            if m.get("tool_calls"):
                pm["tool_calls"] = m["tool_calls"]
            if m.get("tool_call_id"):
                pm["tool_call_id"] = m["tool_call_id"]
            payload_messages.append(pm)
        payload: dict = {"model": chosen, "messages": payload_messages, **openai_gen_params(params)}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        code, body, err = safe_request(
            "POST",
            f"{self.base_url(public)}/chat/completions",
            headers=self._headers(key),
            json=payload,
            timeout=30.0 if tools else DEFAULT_TIMEOUT,
        )
        if err:
            return ChatResult(False, error=network_error_message(err))
        if code == 200 and body:
            try:
                msg = body["choices"][0]["message"]
                calls = []
                for tc in msg.get("tool_calls") or []:
                    fn = (tc or {}).get("function") or {}
                    if fn.get("name"):
                        calls.append({
                            "id": tc.get("id") or "",
                            "name": fn["name"],
                            "arguments": fn.get("arguments") or "{}",
                        })
                return ChatResult(True, content=msg.get("content") or "", tool_calls=calls or None)
            except (KeyError, IndexError, TypeError):
                return ChatResult(False, error="the provider returned an unexpected response")
        return ChatResult(False, error=chat_error_message(code, body))
