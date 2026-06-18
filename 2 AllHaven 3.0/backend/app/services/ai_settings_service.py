"""Workspace AI chat behavior + tool settings.

Stored per-workspace in ``integration_configs`` under reserved provider ids
(same pattern as ``ai_policy_service``), so no migration is needed:

    * ``ai_chat_settings`` — multi-agent defaults, debate-flow visibility,
      human-approval requirement, tool activity visibility, polish level.
    * ``ai_tool_settings`` — per-tool enable/disable overrides (default: enabled).

Safety: ``require_approval`` defaults to True. Even when a workspace turns it
off, HIGH-risk tools STILL require human approval (enforced in the tool
registry) — destructive actions can never run silently.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationAppError
from app.core.principal import Principal
from app.domain.integrations import IntegrationConfig

CHAT_SETTINGS_PROVIDER_ID = "ai_chat_settings"
TOOL_SETTINGS_PROVIDER_ID = "ai_tool_settings"
MEMORY_SETTINGS_PROVIDER_ID = "ai_memory_settings"

CHAT_MODES = ("parallel", "debate", "reasoning", "single")
POLISH_LEVELS = ("standard", "high")

CHAT_DEFAULTS = {
    "default_mode": "single",
    "show_debate_flow": True,   # preserve existing behavior (full transcript shown)
    "require_approval": True,   # write actions create pending proposals by default
    "show_tool_activity": True,
    "polish_level": "standard",
    "max_active_agents": 7,     # hard product cap; users may lower it
}

MEMORY_DEFAULTS = {
    "auto_learning_enabled": True,
    "require_approval_sensitive": True,
}


def _row(db: Session, principal: Principal, provider_id: str) -> Optional[IntegrationConfig]:
    return db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == principal.workspace_id,
            IntegrationConfig.provider_id == provider_id,
        )
    )


def _ensure_row(db: Session, principal: Principal, provider_id: str, display_name: str) -> IntegrationConfig:
    row = _row(db, principal, provider_id)
    if row is None:
        row = IntegrationConfig(
            workspace_id=principal.workspace_id,
            provider_id=provider_id,
            provider_type="settings",
            display_name=display_name,
            created_by=principal.user_id,
            enabled=True,
            status="configured",
            public_config={},
            encrypted_secrets={},
        )
        db.add(row)
        db.flush()
    return row


# --- chat behavior settings -------------------------------------------------


def get_chat_settings(db: Session, principal: Principal) -> dict:
    row = _row(db, principal, CHAT_SETTINGS_PROVIDER_ID)
    stored = row.public_config if (row and isinstance(row.public_config, dict)) else {}
    merged = {**CHAT_DEFAULTS, **{k: v for k, v in stored.items() if k in CHAT_DEFAULTS}}
    # Clamp anything that may have been stored before validation existed.
    merged["max_active_agents"] = max(1, min(int(merged.get("max_active_agents") or 7), 7))
    if merged.get("default_mode") not in CHAT_MODES:
        merged["default_mode"] = CHAT_DEFAULTS["default_mode"]
    if merged.get("polish_level") not in POLISH_LEVELS:
        merged["polish_level"] = CHAT_DEFAULTS["polish_level"]
    return merged


def set_chat_settings(db: Session, principal: Principal, updates: dict) -> dict:
    if not isinstance(updates, dict) or not updates:
        raise ValidationAppError("No settings provided.")
    clean: dict = {}
    for key, value in updates.items():
        if key not in CHAT_DEFAULTS:
            raise ValidationAppError(f"Unknown chat setting '{key}'.")
        if key in ("show_debate_flow", "require_approval", "show_tool_activity"):
            clean[key] = bool(value)
        elif key == "default_mode":
            if value not in CHAT_MODES:
                raise ValidationAppError(f"default_mode must be one of {CHAT_MODES}.")
            clean[key] = value
        elif key == "polish_level":
            if value not in POLISH_LEVELS:
                raise ValidationAppError(f"polish_level must be one of {POLISH_LEVELS}.")
            clean[key] = value
        elif key == "max_active_agents":
            try:
                n = int(value)
            except (TypeError, ValueError):
                raise ValidationAppError("max_active_agents must be a number.")
            if not 1 <= n <= 7:
                raise ValidationAppError("max_active_agents must be between 1 and 7.")
            clean[key] = n
    row = _ensure_row(db, principal, CHAT_SETTINGS_PROVIDER_ID, "AI Chat Behavior")
    row.public_config = {**(row.public_config or {}), **clean}
    row.updated_by = principal.user_id
    db.commit()
    return get_chat_settings(db, principal)


def approval_required(db: Session, principal: Principal) -> bool:
    return bool(get_chat_settings(db, principal)["require_approval"])


# --- per-tool enable/disable -------------------------------------------------


def disabled_tools(db: Session, principal: Principal) -> set[str]:
    row = _row(db, principal, TOOL_SETTINGS_PROVIDER_ID)
    stored = row.public_config if (row and isinstance(row.public_config, dict)) else {}
    disabled = stored.get("disabled") or []
    return {str(t) for t in disabled} if isinstance(disabled, list) else set()


def is_tool_enabled(db: Session, principal: Principal, tool_name: str) -> bool:
    return tool_name not in disabled_tools(db, principal)


def set_tool_enabled(db: Session, principal: Principal, tool_name: str, enabled: bool) -> set[str]:
    row = _ensure_row(db, principal, TOOL_SETTINGS_PROVIDER_ID, "AI Tool Settings")
    config = dict(row.public_config or {})
    disabled = {str(t) for t in (config.get("disabled") or [])}
    if enabled:
        disabled.discard(tool_name)
    else:
        disabled.add(tool_name)
    config["disabled"] = sorted(disabled)
    row.public_config = config
    row.updated_by = principal.user_id
    db.commit()
    return disabled


# --- memory auto-learning settings ------------------------------------------


def get_memory_settings(db: Session, principal: Principal) -> dict:
    row = _row(db, principal, MEMORY_SETTINGS_PROVIDER_ID)
    cfg = dict(row.public_config) if row and row.public_config else {}
    return {**MEMORY_DEFAULTS, **{k: v for k, v in cfg.items() if k in MEMORY_DEFAULTS}}


def set_memory_settings(db: Session, principal: Principal, updates: dict) -> dict:
    row = _ensure_row(db, principal, MEMORY_SETTINGS_PROVIDER_ID, "AI Memory Settings")
    valid_keys = set(MEMORY_DEFAULTS.keys())
    cfg = dict(row.public_config or {})
    for k, v in updates.items():
        if k in valid_keys:
            cfg[k] = v
    row.public_config = cfg
    row.updated_by = principal.user_id
    db.commit()
    return {**MEMORY_DEFAULTS, **{k: v for k, v in cfg.items() if k in MEMORY_DEFAULTS}}


def is_memory_auto_learning_enabled(db: Session, principal: Principal) -> bool:
    settings = get_memory_settings(db, principal)
    return bool(settings.get("auto_learning_enabled", True))


def is_memory_require_approval_sensitive(db: Session, principal: Principal) -> bool:
    settings = get_memory_settings(db, principal)
    return bool(settings.get("require_approval_sensitive", True))
