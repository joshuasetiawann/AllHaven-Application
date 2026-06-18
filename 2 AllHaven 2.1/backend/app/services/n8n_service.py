"""Live n8n integration: list workflows and toggle their active state.

Uses the workspace's configured n8n **Base URL + API key** (server-side only;
the key is never returned to the client). n8n's Public API requires the
``X-N8N-API-KEY`` header and the Public API feature enabled, so we report honest
statuses: ``not_configured`` / ``no_api_key`` / ``unavailable`` /
``unauthorized`` / ``error`` / ``online``.

Scope is read + manage: list workflows and activate/deactivate them. There is no
generic "run" endpoint in the n8n public API (only webhook-triggered flows can be
fired by URL), so we don't pretend to offer one.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationAppError
from app.core.principal import Principal
from app.services import integration_config_service as ics
from app.services.ai_providers.base import safe_request

_API = "/api/v1"
_TIMEOUT = 10.0


def _resolve(db: Session, principal: Principal) -> tuple[str, str]:
    public, secrets = ics.effective_config(db, principal, "n8n")
    return (public.get("base_url") or "").rstrip("/"), (secrets.get("api_key") or "")


def _headers(key: str) -> dict:
    return {"X-N8N-API-KEY": key, "accept": "application/json"}


def _interpret(code: int | None, err: str) -> tuple[str, str]:
    if err or code is None:
        return "unavailable", f"Could not reach n8n: {err or 'no response'}"
    if code in (401, 403):
        return "unauthorized", "n8n rejected the API key. Check the key and that n8n's Public API is enabled."
    if code == 404:
        return "error", "n8n API not found (HTTP 404). Enable the Public API on your n8n instance."
    if code >= 400:
        return "error", f"n8n returned an error (HTTP {code})."
    return "online", ""


def list_workflows(db: Session, principal: Principal) -> dict:
    """List the workspace's n8n workflows (honest status, never raises)."""
    base, key = _resolve(db, principal)
    if not base:
        return {"status": "not_configured", "message": "Set the n8n Base URL in Settings → Connected Tools.", "base_url": "", "workflows": []}
    if not key:
        return {"status": "no_api_key", "message": "Add your n8n API key in Settings → Connected Tools (and enable n8n's Public API).", "base_url": base, "workflows": []}

    code, body, err = safe_request("GET", f"{base}{_API}/workflows", headers=_headers(key), params={"limit": 100}, timeout=_TIMEOUT)
    status, message = _interpret(code, err)
    if status != "online":
        return {"status": status, "message": message, "base_url": base, "workflows": []}

    items = body.get("data", []) if isinstance(body, dict) else []
    workflows = [
        {
            "id": str(w.get("id")),
            "name": w.get("name") or "(untitled)",
            "active": bool(w.get("active")),
            "updated_at": w.get("updatedAt"),
        }
        for w in items if isinstance(w, dict) and w.get("id") is not None
    ]
    return {"status": "online", "message": "", "base_url": base, "workflows": workflows}


def set_active(db: Session, principal: Principal, workflow_id: str, active: bool) -> dict:
    """Activate/deactivate a workflow via the n8n public API. Honest on failure."""
    base, key = _resolve(db, principal)
    if not base or not key:
        raise ValidationAppError("n8n needs both a Base URL and an API key (Settings → Connected Tools).")
    action = "activate" if active else "deactivate"
    code, body, err = safe_request("POST", f"{base}{_API}/workflows/{workflow_id}/{action}", headers=_headers(key), timeout=_TIMEOUT)
    status, message = _interpret(code, err)
    if status != "online":
        raise ValidationAppError(message)
    w = body if isinstance(body, dict) else {}
    return {"id": str(w.get("id", workflow_id)), "name": w.get("name"), "active": bool(w.get("active", active))}
