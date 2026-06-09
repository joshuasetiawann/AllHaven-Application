"""AI provider router.

Workspace-scoped configuration of AI agents (5 API providers + local Ollama) and
provider-agnostic chat routing. Enforces the safety policy:
    * External providers are blocked when AI_ALLOW_EXTERNAL_PROVIDERS is false.
    * Local Ollama works without external permission.
    * Secrets are encrypted at rest and never returned raw.
    * The router only generates replies; it never executes writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.principal import Principal
from app.domain.integrations import AiAgentConfig
from app.services import ai_policy_service
from app.services import config_common as cc
from app.services import env_file_service
from app.services.ai_providers.anthropic_provider import AnthropicProvider
from app.services.ai_providers.base import AIProvider
from app.services.ai_providers.blackbox_provider import BlackboxProvider
from app.services.ai_providers.gemini_provider import GeminiProvider
from app.services.ai_providers.grok_provider import GrokProvider
from app.services.ai_providers.ollama_provider import OllamaProvider
from app.services.ai_providers.openai_provider import OpenAIProvider
from app.services.ai_providers.openrouter_provider import OpenRouterProvider
from app.services.audit_service import write_audit
from app.services.integration_status_service import is_configured_value
from app.services.provider_registry import AI_PROVIDERS, ProviderSpec, get_ai_provider_spec

ADAPTERS: dict[str, AIProvider] = {
    "ollama": OllamaProvider(),
    "openai": OpenAIProvider(),
    "anthropic": AnthropicProvider(),
    "gemini": GeminiProvider(),
    "grok": GrokProvider(),
    "blackbox": BlackboxProvider(),
    # Three independent OpenRouter slots share the OpenRouter adapter; each has
    # its own DB row, key, status, and default model.
    "openrouter_1": OpenRouterProvider(),
    "openrouter_2": OpenRouterProvider(),
    "openrouter_3": OpenRouterProvider(),
}


# --- env fallback ---------------------------------------------------------


def _env_public(spec: ProviderSpec) -> dict:
    mapping = {
        "ollama": {"base_url": settings.OLLAMA_BASE_URL, "default_model": settings.OLLAMA_DEFAULT_MODEL},
        "openai": {"default_model": settings.OPENAI_DEFAULT_MODEL},
        "anthropic": {"default_model": settings.ANTHROPIC_DEFAULT_MODEL},
        "gemini": {"default_model": settings.GEMINI_DEFAULT_MODEL},
        "grok": {"default_model": settings.GROK_DEFAULT_MODEL},
        "blackbox": {"default_model": settings.BLACKBOX_DEFAULT_MODEL},
        "openrouter_1": {"default_model": settings.OPENROUTER_1_DEFAULT_MODEL or settings.OPENROUTER_DEFAULT_MODEL},
        "openrouter_2": {"default_model": settings.OPENROUTER_2_DEFAULT_MODEL},
        "openrouter_3": {"default_model": settings.OPENROUTER_3_DEFAULT_MODEL},
    }
    return {k: v for k, v in mapping.get(spec.id, {}).items() if is_configured_value(v)}


def _env_secrets(spec: ProviderSpec) -> dict:
    mapping = {
        "openai": {"api_key": settings.OPENAI_API_KEY},
        "anthropic": {"api_key": settings.ANTHROPIC_API_KEY},
        "gemini": {"api_key": settings.GEMINI_API_KEY},
        "grok": {"api_key": settings.GROK_API_KEY},
        "blackbox": {"api_key": settings.BLACKBOX_API_KEY},
        # Slot 1 falls back to the legacy single OPENROUTER_API_KEY.
        "openrouter_1": {"api_key": settings.OPENROUTER_1_API_KEY or settings.OPENROUTER_API_KEY},
        "openrouter_2": {"api_key": settings.OPENROUTER_2_API_KEY},
        "openrouter_3": {"api_key": settings.OPENROUTER_3_API_KEY},
    }
    return {k: v for k, v in mapping.get(spec.id, {}).items() if is_configured_value(v)}


# --- rows -----------------------------------------------------------------


def _get_row(db: Session, principal: Principal, provider_id: str) -> Optional[AiAgentConfig]:
    return db.scalar(
        select(AiAgentConfig).where(
            AiAgentConfig.workspace_id == principal.workspace_id,
            AiAgentConfig.provider_id == provider_id,
        )
    )


def _get_or_create_row(db: Session, principal: Principal, spec: ProviderSpec) -> AiAgentConfig:
    row = _get_row(db, principal, spec.id)
    if row is None:
        row = AiAgentConfig(
            workspace_id=principal.workspace_id,
            provider_id=spec.id,
            provider_type=spec.provider_type,
            agent_name=spec.name,
            created_by=principal.user_id,
            # Local providers are usable once configured; external providers are
            # disabled by default until the user explicitly enables them.
            enabled=not spec.external,
            status="not_configured",
            privacy_mode=settings.AI_DEFAULT_PRIVACY_MODE,
            default_model=spec.default_model or None,
            public_config={},
            encrypted_secrets={},
        )
        db.add(row)
        db.flush()
    return row


def _effective_config(row: Optional[AiAgentConfig], spec: ProviderSpec) -> tuple[dict, dict]:
    public = dict(_env_public(spec))
    secrets = dict(_env_secrets(spec))
    if row is not None:
        public.update(row.public_config or {})
        if row.default_model:
            public["default_model"] = row.default_model
        decrypted = cc.decrypt_all(row, spec.secret_fields())
        secrets.update({k: v for k, v in decrypted.items() if v})
    return public, secrets


# --- views ----------------------------------------------------------------


def _view(spec: ProviderSpec, row: Optional[AiAgentConfig]) -> dict:
    adapter = ADAPTERS[spec.id]
    if row is not None:
        status = row.status
        enabled = row.enabled
        public = dict(row.public_config or {})
        secrets = cc.secret_previews(row, spec)
        default_model = row.default_model or spec.default_model
        privacy_mode = row.privacy_mode
        last_verified = row.last_verified_at.isoformat() if row.last_verified_at else None
        last_error = row.last_error
    else:
        env_pub = _env_public(spec)
        env_sec = _env_secrets(spec)
        configured_by_env = bool(env_sec) if spec.api_key_required else bool(env_pub.get("base_url"))
        status = "configured" if configured_by_env else "not_configured"
        enabled = False
        public = env_pub
        secrets = {f: {"configured": bool(env_sec.get(f)), "preview": ""} for f in spec.secret_fields()}
        default_model = env_pub.get("default_model") or spec.default_model
        privacy_mode = settings.AI_DEFAULT_PRIVACY_MODE
        last_verified = None
        last_error = None

    configured = status in cc.HAS_CONFIG_STATUSES
    return {
        "id": spec.id,
        "provider_id": spec.id,
        "name": spec.name,
        "purpose": spec.purpose,
        "provider_type": spec.provider_type,
        "external": spec.external,
        "api_key_required": spec.api_key_required,
        "enabled": enabled,
        "status": status,
        "configured": configured,
        "detail": cc.STATUS_DETAIL.get(status, "Not configured"),
        "default_model": default_model,
        "privacy_mode": privacy_mode,
        "fields": cc.field_specs(spec),
        "public_config": public,
        "secrets": secrets,
        "last_verified_at": last_verified,
        "last_error": last_error,
    }


def _require_spec(provider_id: str) -> ProviderSpec:
    spec = get_ai_provider_spec(provider_id)
    if spec is None:
        raise NotFoundError(f"Unknown AI provider '{provider_id}'.")
    return spec


def list_providers(db: Session, principal: Principal) -> list[dict]:
    rows = {r.provider_id: r for r in db.scalars(
        select(AiAgentConfig).where(AiAgentConfig.workspace_id == principal.workspace_id)
    ).all()}
    return [_view(spec, rows.get(spec.id)) for spec in AI_PROVIDERS]


def get_provider(db: Session, principal: Principal, provider_id: str) -> dict:
    spec = _require_spec(provider_id)
    return _view(spec, _get_row(db, principal, provider_id))


def upsert_provider(
    db: Session,
    principal: Principal,
    provider_id: str,
    *,
    public: dict,
    secrets: dict,
    default_model: Optional[str] = None,
    privacy_mode: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    enabled: Optional[bool] = None,
) -> dict:
    spec = _require_spec(provider_id)
    row = _get_or_create_row(db, principal, spec)
    cc.apply_public_updates(row, spec, public or {})
    cc.apply_secret_updates(row, spec, secrets or {})
    if default_model is not None:
        row.default_model = default_model or None
    if privacy_mode is not None:
        row.privacy_mode = privacy_mode
    if system_prompt is not None:
        row.system_prompt = system_prompt or None
    if temperature is not None:
        row.temperature = Decimal(str(temperature))
    if enabled is not None:
        row.enabled = enabled
    row.updated_by = principal.user_id
    row.status = cc.saved_status(row, spec)
    row.last_error = None
    row.last_verified_at = None
    db.flush()
    write_audit(db, action="UPDATE", entity_name="ai_agent_config",
                workspace_id=principal.workspace_id, user_id=principal.user_id, entity_id=row.id,
                meta={"provider_id": provider_id, "status": row.status})
    db.commit()
    db.refresh(row)
    view = _view(spec, row)
    # Mirror real (non-placeholder) values to the local .env for persistence.
    clean_secrets = {k: v for k, v in (secrets or {}).items() if is_configured_value(v)}
    env_public = dict(public or {})
    if default_model is not None:
        env_public["default_model"] = default_model
    env_updates = env_file_service.map_ai_provider_updates(provider_id, env_public, clean_secrets)
    view["env_sync"] = env_file_service.sync_env(env_updates)
    return view


def test_provider(db: Session, principal: Principal, provider_id: str) -> dict:
    spec = _require_spec(provider_id)
    row = _get_or_create_row(db, principal, spec)
    public, secrets = _effective_config(row, spec)
    adapter = ADAPTERS[spec.id]
    if not adapter.is_configured(public, secrets):
        row.status = "not_configured"
        row.last_error = "Provider is not configured"
    else:
        result = adapter.test_connection(public, secrets)
        # Trust the adapter's honest status; only "online" sets verified time.
        row.status = result.status
        row.last_error = None if result.status == "online" else (result.message or None)
        if result.status == "online":
            row.last_verified_at = datetime.now(timezone.utc)
    db.flush()
    db.commit()
    db.refresh(row)
    return _view(spec, row)


def set_enabled(db: Session, principal: Principal, provider_id: str, enabled: bool) -> dict:
    spec = _require_spec(provider_id)
    row = _get_or_create_row(db, principal, spec)
    row.enabled = enabled
    row.updated_by = principal.user_id
    row.status = cc.saved_status(row, spec)
    db.flush()
    db.commit()
    db.refresh(row)
    return _view(spec, row)


# --- chat routing ---------------------------------------------------------


def resolve_default_provider(db: Session, principal: Principal) -> str:
    default = ai_policy_service.default_provider(db, principal)
    return default if get_ai_provider_spec(default) else "ollama"


@dataclass
class ChatPlan:
    """A resolved decision about whether/how to call one provider.

    All DB access happens while building the plan (on the request thread). The
    ``execute`` closure only touches the captured adapter + plain dicts, so it is
    safe to run inside a worker thread for concurrent multi-agent fan-out.
    """

    provider_id: str
    provider_name: str
    external: bool
    configured: bool
    enabled: bool
    # 'queued' (runnable) | 'blocked' | 'not_configured' | 'disabled' | 'error'
    status: str
    message: str = ""
    _runner: Optional[Callable[[list[dict]], "object"]] = field(default=None, repr=False)

    @property
    def runnable(self) -> bool:
        return self.status == "queued"

    def execute(self, messages: list[dict]):
        """Run the network call. Returns a ChatResult. Thread-safe."""
        return self._runner(messages)


def plan_chat(db: Session, principal: Principal, provider_id: Optional[str] = None) -> ChatPlan:
    """Resolve a provider into an honest, ready-to-run plan (no network here)."""
    pid = provider_id or resolve_default_provider(db, principal)
    spec = get_ai_provider_spec(pid)
    if spec is None:
        return ChatPlan(pid, pid, False, False, False, "error", f"Unknown AI provider '{pid}'.")

    adapter = ADAPTERS[pid]
    row = _get_row(db, principal, pid)
    public, secrets = _effective_config(row, spec)
    configured = adapter.is_configured(public, secrets)
    enabled = bool(row.enabled) if row is not None else False
    model = row.default_model if row is not None else None

    if spec.external and not ai_policy_service.is_external_allowed(db, principal):
        return ChatPlan(
            pid, spec.name, spec.external, configured, enabled, "blocked",
            (
                f"External AI provider '{spec.name}' is blocked. Turn on "
                "“Allow external AI providers” in Settings → Privacy & Safety (or set "
                "AI_ALLOW_EXTERNAL_PROVIDERS=true) to use it, and only send non-confidential "
                "data. CoreOS never sends data to external AI unless you allow it."
            ),
        )
    if not configured:
        return ChatPlan(
            pid, spec.name, spec.external, False, enabled, "not_configured",
            (
                f"The '{spec.name}' provider is not configured. Add its credentials in Settings → "
                "AI Providers. CoreOS will never fake AI responses."
            ),
        )
    if not enabled:
        return ChatPlan(
            pid, spec.name, spec.external, True, False, "disabled",
            f"The '{spec.name}' provider is configured but disabled. Enable it in Settings to use it.",
        )

    def _run(messages: list[dict]):
        return adapter.chat(public, secrets, messages, model=model)

    return ChatPlan(pid, spec.name, spec.external, True, True, "queued", "", _run)


def run_chat(
    db: Session,
    principal: Principal,
    *,
    messages: list[dict],
    provider_id: Optional[str] = None,
) -> dict:
    """Route a chat to the selected/default provider. Honest, no fake success."""
    plan = plan_chat(db, principal, provider_id)
    pid = plan.provider_id
    if plan.status == "error" and not plan.runnable and plan.provider_name == pid:
        return {"ok": False, "provider_id": pid, "configured": False, "blocked": False,
                "content": plan.message, "error": "unknown_provider"}
    if plan.status == "blocked":
        return {"ok": False, "provider_id": pid, "configured": plan.configured, "blocked": True,
                "content": plan.message, "error": "external_disabled"}
    if plan.status == "not_configured":
        return {"ok": False, "provider_id": pid, "configured": False, "blocked": False,
                "content": plan.message, "error": "not_configured"}
    if plan.status == "disabled":
        return {"ok": False, "provider_id": pid, "configured": True, "blocked": False,
                "content": plan.message, "error": "disabled"}

    result = plan.execute(messages)
    if result.ok:
        return {"ok": True, "provider_id": pid, "configured": True, "blocked": False,
                "content": result.content, "error": ""}
    return {
        "ok": False, "provider_id": pid, "configured": True, "blocked": False,
        "content": f"The '{plan.provider_name}' provider could not complete the request: {result.error}",
        "error": result.error,
    }
