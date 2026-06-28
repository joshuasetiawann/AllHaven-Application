"""Desktop Bridge connection resolver (v4.0).

Desktop-local services (Ollama, n8n) can be reached several ways depending on where
the client is:
  * local_desktop    → localhost on the desktop machine itself
  * tailscale_private → the desktop's Tailscale device IP / MagicDNS host
  * tailscale_serve   → a Tailscale Serve URL (private inside the tailnet)
  * tailscale_funnel  → a PUBLIC Tailscale Funnel URL (disabled unless explicitly confirmed)
  * auto              → first configured of local → private → serve (never auto-funnel)

This module ONLY resolves which URL to use for a given config — it performs no I/O.
Reachability/online status is decided by the verify step that tests the resolved URL,
so status is always honest (online only if the resolved endpoint actually responds).
"""
from __future__ import annotations

from typing import Optional, Tuple

CONNECTION_MODES = (
    "local_desktop",
    "tailscale_private",
    "tailscale_serve",
    "tailscale_funnel",
    "auto",
)
DEFAULT_MODE = "local_desktop"

# Fields (in priority order) that hold the URL for each mode. `base_url` is the legacy
# field kept for back-compat with pre-v4 single-URL configs.
_MODE_FIELDS = {
    "local_desktop": ("local_url", "base_url"),
    "tailscale_private": ("tailscale_url",),
    "tailscale_serve": ("serve_url",),
    "tailscale_funnel": ("funnel_url",),
}
# auto never tries funnel (public) — only private endpoints.
_AUTO_ORDER = ("local_desktop", "tailscale_private", "tailscale_serve")


def funnel_enabled(public: dict) -> bool:
    return str(public.get("funnel_enabled") or "").strip().lower() in ("1", "true", "yes", "on")


def _url_for_mode(public: dict, mode: str) -> Optional[str]:
    for field in _MODE_FIELDS.get(mode, ()):
        v = (str(public.get(field) or "")).strip().rstrip("/")
        if v:
            return v
    return None


def resolve(public: dict) -> Tuple[Optional[str], str, Optional[str]]:
    """Resolve the effective endpoint for a desktop-local service config.

    Returns (url, mode_used, reason):
      * url        — the resolved base URL, or None if none is usable.
      * mode_used  — the connection mode applied.
      * reason     — None on success, else a short human reason why url is None
                     (e.g. funnel not enabled, no URL set for the mode).
    """
    mode = (str(public.get("connection_mode") or "")).strip().lower() or DEFAULT_MODE
    if mode not in CONNECTION_MODES:
        mode = DEFAULT_MODE

    if mode == "auto":
        for m in _AUTO_ORDER:
            url = _url_for_mode(public, m)
            if url:
                return url, m, None
        return None, "auto", "No Local/Tailscale endpoint is configured."

    if mode == "tailscale_funnel" and not funnel_enabled(public):
        return None, mode, "Funnel (public) mode is not enabled — confirm it in Settings first."

    url = _url_for_mode(public, mode)
    if not url:
        return None, mode, f"No URL set for the '{mode}' connection mode."
    return url, mode, None
