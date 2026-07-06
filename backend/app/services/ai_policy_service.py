"""Workspace-level AI policy (e.g. whether external providers are allowed).

Stored per-workspace in the integration_configs table under a reserved provider
id, so no extra migration is needed. Falls back to the env default
(AI_ALLOW_EXTERNAL_PROVIDERS) when the workspace hasn't set a preference.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.principal import Principal
from app.domain.integrations import IntegrationConfig

POLICY_PROVIDER_ID = "ai_policy"


def _row(db: Session, principal: Principal) -> Optional[IntegrationConfig]:
    return db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == principal.workspace_id,
            IntegrationConfig.provider_id == POLICY_PROVIDER_ID,
        )
    )


def get_policy(db: Session, principal: Principal) -> dict:
    row = _row(db, principal)
    config = row.public_config if (row and isinstance(row.public_config, dict)) else {}
    if "allow_external" in config:
        allow_external = bool(config["allow_external"])
    else:
        allow_external = settings.AI_ALLOW_EXTERNAL_PROVIDERS
    return {
        "allow_external": allow_external,
        "default_privacy_mode": settings.AI_DEFAULT_PRIVACY_MODE,
        "env_default": settings.AI_ALLOW_EXTERNAL_PROVIDERS,
    }


def is_external_allowed(db: Session, principal: Principal) -> bool:
    return get_policy(db, principal)["allow_external"]


def set_allow_external(db: Session, principal: Principal, allow_external: bool) -> dict:
    row = _row(db, principal)
    if row is None:
        row = IntegrationConfig(
            workspace_id=principal.workspace_id,
            provider_id=POLICY_PROVIDER_ID,
            provider_type="policy",
            display_name="AI Policy",
            created_by=principal.user_id,
            enabled=True,
            status="configured",
            public_config={},
            encrypted_secrets={},
        )
        db.add(row)
        db.flush()
    config = dict(row.public_config or {})
    config["allow_external"] = bool(allow_external)
    row.public_config = config
    row.updated_by = principal.user_id
    db.commit()
    return get_policy(db, principal)
