"""Integration configuration service.

Workspace-scoped CRUD for tool/infrastructure integrations with:
    * encrypted secret storage (never returned raw — masked previews only)
    * honest status (online only after a successful verification)
    * connection testing via safe HTTP/DB checks
    * .env fallback for backward compatibility when no DB row exists yet
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.principal import Principal
from app.domain.integrations import IntegrationConfig
from app.services import config_common as cc
from app.services.ai_providers.base import safe_request
from app.services.audit_service import write_audit
from app.services.integration_status_service import is_configured_value
from app.services.provider_registry import INTEGRATIONS, ProviderSpec, get_integration_spec

GROUP_BY_TYPE = {
    "system": "infrastructure",
    "local_ai": "local_ai",
    "automation": "automation",
    "auth_storage": "auth_storage",
    "calendar": "calendar",
    "weather": "weather",
}


# --- env fallback ---------------------------------------------------------


def _env_public(spec: ProviderSpec) -> dict:
    mapping = {
        "ollama": {"base_url": settings.OLLAMA_BASE_URL, "default_model": settings.OLLAMA_DEFAULT_MODEL},
        "n8n": {"base_url": settings.N8N_BASE_URL},
        "supabase": {"url": settings.SUPABASE_URL, "anon_key": settings.SUPABASE_ANON_KEY},
        "google_calendar": {"client_id": settings.GOOGLE_CALENDAR_CLIENT_ID},
        "weather_api": {"provider": "openweathermap"},
    }
    return {k: v for k, v in mapping.get(spec.id, {}).items() if is_configured_value(v)}


def _env_secret_present(spec: ProviderSpec) -> dict:
    mapping = {"weather_api": {"api_key": settings.WEATHER_API_KEY}}
    return {k: v for k, v in mapping.get(spec.id, {}).items() if is_configured_value(v)}


def _env_configured(spec: ProviderSpec) -> bool:
    pub = _env_public(spec)
    sec = _env_secret_present(spec)
    secret_keys = set(spec.secret_fields())
    for field in spec.required_fields():
        if field in secret_keys:
            if not sec.get(field):
                return False
        elif not pub.get(field):
            return False
    return bool(pub or sec)


# --- rows -----------------------------------------------------------------


def _get_row(db: Session, principal: Principal, provider_id: str) -> Optional[IntegrationConfig]:
    return db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == principal.workspace_id,
            IntegrationConfig.provider_id == provider_id,
        )
    )


def _get_or_create_row(db: Session, principal: Principal, spec: ProviderSpec) -> IntegrationConfig:
    row = _get_row(db, principal, spec.id)
    if row is None:
        row = IntegrationConfig(
            workspace_id=principal.workspace_id,
            provider_id=spec.id,
            provider_type=spec.provider_type,
            display_name=spec.name,
            created_by=principal.user_id,
            public_config={},
            encrypted_secrets={},
            enabled=True,
            status="not_configured",
        )
        db.add(row)
        db.flush()
    return row


# --- verification ---------------------------------------------------------


def _effective_config(row: Optional[IntegrationConfig], spec: ProviderSpec) -> tuple[dict, dict]:
    """Merge env defaults with the saved row (row wins)."""
    public = dict(_env_public(spec))
    secrets = dict(_env_secret_present(spec))
    if row is not None:
        public.update(row.public_config or {})
        secrets.update(cc.decrypt_all(row, spec.secret_fields()))
        secrets = {k: v for k, v in secrets.items() if v}
    return public, secrets


def _verify(db: Session, spec: ProviderSpec, public: dict, secrets: dict) -> tuple[str, str]:
    """Return (status, error). status in {online, error, configured}."""
    pid = spec.id
    if pid == "postgresql":
        try:
            db.execute(text("SELECT 1"))
            return "online", ""
        except Exception as exc:  # noqa: BLE001
            return "error", str(exc)[:200]

    if pid == "ollama":
        base = (public.get("base_url") or "").rstrip("/")
        if not base:
            return "error", "Base URL not set"
        code, _, err = safe_request("GET", f"{base}/api/tags")
        return ("online", "") if code == 200 else ("error", err or f"HTTP {code}")

    if pid == "n8n":
        base = (public.get("base_url") or "").rstrip("/")
        if not base:
            return "error", "Base URL not set"
        code, _, err = safe_request("GET", f"{base}/healthz")
        if code is None:
            code, _, err = safe_request("GET", base)
        return ("online", "") if code and 200 <= code < 500 else ("error", err or f"HTTP {code}")

    if pid == "supabase":
        url = (public.get("url") or "").rstrip("/")
        anon = secrets.get("anon_key") or public.get("anon_key") or ""
        if not url:
            return "error", "Project URL not set"
        headers = {"apikey": anon} if anon else None
        code, _, err = safe_request("GET", f"{url}/auth/v1/health", headers=headers)
        return ("online", "") if code and 200 <= code < 500 else ("error", err or f"HTTP {code}")

    if pid == "google_calendar":
        # OAuth is intentionally not implemented; honest "configured", never online.
        if public.get("client_id") and public.get("redirect_uri"):
            return "configured", "OAuth verification not implemented in MVP"
        return "error", "client_id and redirect_uri are required"

    if pid == "weather_api":
        key = secrets.get("api_key") or ""
        if not key:
            return "error", "API key not set"
        provider = (public.get("provider") or "openweathermap").lower()
        if provider == "openweathermap":
            loc = public.get("default_location") or "Jakarta"
            code, _, err = safe_request(
                "GET",
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": loc, "appid": key},
            )
            return ("online", "") if code == 200 else ("error", err or f"HTTP {code}")
        return "configured", "Verification not implemented for this provider"

    return "configured", ""


# --- views ----------------------------------------------------------------


def _view(db: Session, principal: Principal, spec: ProviderSpec, row: Optional[IntegrationConfig]) -> dict:
    group = GROUP_BY_TYPE.get(spec.provider_type, "other")

    # PostgreSQL: system, live-checked, not user-editable.
    if spec.id == "postgresql":
        status, _ = _verify(db, spec, {}, {})
        return _base_view(spec, group, enabled=True, status=status, public={}, secrets={},
                          last_verified_at=None, last_error=None)

    if row is not None:
        status = row.status
        public = {k: v for k, v in (row.public_config or {}).items()}
        secrets = cc.secret_previews(row, spec)
        return _base_view(spec, group, enabled=row.enabled, status=status, public=public,
                          secrets=secrets, last_verified_at=row.last_verified_at, last_error=row.last_error)

    # No DB row: fall back to env.
    if _env_configured(spec):
        env_pub = _env_public(spec)
        env_sec = _env_secret_present(spec)
        secrets = {f: {"configured": bool(env_sec.get(f)), "preview": ""} for f in spec.secret_fields()}
        return _base_view(spec, group, enabled=True, status="configured", public=env_pub,
                          secrets=secrets, last_verified_at=None, last_error=None, source="env")

    secrets = {f: {"configured": False, "preview": ""} for f in spec.secret_fields()}
    return _base_view(spec, group, enabled=True, status="not_configured", public={},
                      secrets=secrets, last_verified_at=None, last_error=None)


def _base_view(spec, group, *, enabled, status, public, secrets, last_verified_at, last_error, source="db") -> dict:
    configured = status in ("configured", "online")
    detail = cc.STATUS_DETAIL.get(status, "Not configured")
    if spec.id == "postgresql" and status == "online":
        detail = "Connected"
    return {
        # Backward-compatible fields used by existing UI:
        "key": spec.id,
        "name": spec.name,
        "status": status,
        "configured": configured,
        "detail": detail,
        # Rich fields:
        "id": spec.id,
        "provider_type": spec.provider_type,
        "group": group,
        "purpose": spec.purpose,
        "editable": spec.editable,
        "api_key_required": spec.api_key_required,
        "enabled": enabled,
        "fields": cc.field_specs(spec),
        "public_config": public,
        "secrets": secrets,
        "last_verified_at": last_verified_at.isoformat() if last_verified_at else None,
        "last_error": last_error,
        "source": source,
    }


def list_integrations(db: Session, principal: Principal) -> list[dict]:
    rows = {r.provider_id: r for r in db.scalars(
        select(IntegrationConfig).where(IntegrationConfig.workspace_id == principal.workspace_id)
    ).all()}
    return [_view(db, principal, spec, rows.get(spec.id)) for spec in INTEGRATIONS]


def _require_spec(provider_id: str) -> ProviderSpec:
    spec = get_integration_spec(provider_id)
    if spec is None:
        raise NotFoundError(f"Unknown integration '{provider_id}'.")
    return spec


def get_integration(db: Session, principal: Principal, provider_id: str) -> dict:
    spec = _require_spec(provider_id)
    return _view(db, principal, spec, _get_row(db, principal, provider_id))


def upsert_integration(db: Session, principal: Principal, provider_id: str, public: dict, secrets: dict) -> dict:
    spec = _require_spec(provider_id)
    if not spec.editable:
        raise ForbiddenError("This integration is managed by the system and cannot be edited.")
    row = _get_or_create_row(db, principal, spec)
    cc.apply_public_updates(row, spec, public or {})
    cc.apply_secret_updates(row, spec, secrets or {})
    row.updated_by = principal.user_id
    # Saving never implies 'online' — re-verification is required.
    row.status = cc.saved_status(row, spec)
    row.last_error = None
    row.last_verified_at = None
    db.flush()
    write_audit(db, action="UPDATE", entity_name="integration_config",
                workspace_id=principal.workspace_id, user_id=principal.user_id, entity_id=row.id,
                meta={"provider_id": provider_id, "status": row.status})
    db.commit()
    db.refresh(row)
    return _view(db, principal, spec, row)


def test_integration(db: Session, principal: Principal, provider_id: str) -> dict:
    spec = _require_spec(provider_id)
    if spec.id == "postgresql":
        return _view(db, principal, spec, None)
    row = _get_or_create_row(db, principal, spec)
    public, secrets = _effective_config(row, spec)
    status, error = _verify(db, spec, public, secrets)
    row.status = status
    row.last_error = error or None
    if status == "online":
        row.last_verified_at = datetime.now(timezone.utc)
    db.flush()
    db.commit()
    db.refresh(row)
    return _view(db, principal, spec, row)


def set_enabled(db: Session, principal: Principal, provider_id: str, enabled: bool) -> dict:
    spec = _require_spec(provider_id)
    if not spec.editable:
        raise ForbiddenError("This integration cannot be enabled/disabled.")
    row = _get_or_create_row(db, principal, spec)
    row.enabled = enabled
    row.updated_by = principal.user_id
    row.status = "disabled" if not enabled else cc.saved_status(row, spec)
    db.flush()
    db.commit()
    db.refresh(row)
    return _view(db, principal, spec, row)


def clear_integration(db: Session, principal: Principal, provider_id: str) -> dict:
    spec = _require_spec(provider_id)
    if not spec.editable:
        raise ForbiddenError("This integration cannot be cleared.")
    row = _get_row(db, principal, provider_id)
    if row is not None:
        row.public_config = {}
        row.encrypted_secrets = {}
        row.status = "not_configured"
        row.last_error = None
        row.last_verified_at = None
        row.enabled = True
        row.updated_by = principal.user_id
        db.flush()
        write_audit(db, action="DELETE", entity_name="integration_config",
                    workspace_id=principal.workspace_id, user_id=principal.user_id, entity_id=row.id,
                    meta={"provider_id": provider_id})
        db.commit()
    return _view(db, principal, spec, _get_row(db, principal, provider_id))
