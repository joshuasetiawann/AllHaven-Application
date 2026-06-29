# backend/app/services/supabase_sync_service.py
"""Optional Supabase sync — runs in background, never blocks main flow.

Enabled by configuring SUPABASE_URL and SUPABASE_ANON_KEY via Settings → Integrations.
Sync direction: local PostgreSQL → Supabase (one-way for now).
All sync errors are silently logged — never raised to callers.

Security:
- The anon key is NEVER logged.
- The anon key is NEVER included in returned messages.
- This module never raises to its callers.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.principal import Principal

log = logging.getLogger(__name__)

SUPABASE_PROVIDER_ID = "supabase"


def _get_credentials(db: Session, principal: Principal) -> tuple[Optional[str], Optional[str]]:
    """Return (supabase_url, anon_key) or (None, None) if not configured/enabled.

    Adaptation from plan: In the AllHaven registry, the Supabase FieldSpec stores
    ``url`` and ``anon_key`` as public (non-secret) fields in ``public_config``.
    Only ``service_role_key`` is stored as an encrypted secret. Therefore:
      - ``url``      → row.public_config["url"]
      - ``anon_key`` → row.public_config["anon_key"]
    The column on IntegrationConfig is ``encrypted_secrets`` (not ``secrets``).
    """
    from sqlalchemy import select

    from app.domain.integrations import IntegrationConfig

    row = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == principal.workspace_id,
            IntegrationConfig.provider_id == SUPABASE_PROVIDER_ID,
            IntegrationConfig.enabled == True,  # noqa: E712
        )
    )
    if not row:
        return None, None

    pub = row.public_config or {}
    url = pub.get("url") or ""
    anon_key = pub.get("anon_key") or ""

    # Also support a service_role_key stored in encrypted_secrets as a fallback
    # (some admins may prefer to use the stronger key for server-side sync).
    if not anon_key and row.encrypted_secrets:
        try:
            from app.core.secrets import decrypt_secret

            raw = row.encrypted_secrets.get("service_role_key")
            if raw:
                anon_key = decrypt_secret(raw)
        except Exception:
            pass

    return url or None, anon_key or None


def is_enabled(db: Session, principal: Principal) -> bool:
    """Return True when valid Supabase credentials are configured and enabled."""
    url, key = _get_credentials(db, principal)
    return bool(url and key)


def sync_all(db: Session, principal: Principal) -> dict:
    """Trigger a one-way background sync (local → Supabase) and return immediately.

    Returns ``{"status": "not_configured", ...}`` when credentials are missing.
    Returns ``{"status": "syncing", ...}`` when a daemon thread has been started.
    Never raises.
    """
    import threading

    url, key = _get_credentials(db, principal)
    if not url or not key:
        return {
            "status": "not_configured",
            "message": "Configure Supabase URL and anon key in Settings → Integrations.",
        }

    workspace_id = str(principal.workspace_id)
    t = threading.Thread(
        target=_sync_thread, args=(url, key, workspace_id), daemon=True
    )
    t.start()
    return {"status": "syncing", "message": "Background sync started."}


def _sync_thread(url: str, key: str, workspace_id: str) -> None:
    """Runs in a daemon thread. Creates its own DB session. Never raises."""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        _do_sync(db, url, key, workspace_id)
    except Exception as exc:
        log.debug("Supabase sync error: %s", exc)
    finally:
        db.close()


def _do_sync(db: Session, url: str, key: str, workspace_id: str) -> None:
    """Attempt to sync AI tables to Supabase using the REST API (no SDK required).

    Uses stdlib ``urllib.request`` POST to ``{url}/rest/v1/{table}`` with the
    ``Prefer: resolution=merge-duplicates`` header so rows are upserted.
    Timeout: 10 s per table request.
    """
    import json
    import urllib.request
    import uuid as _uuid

    ws = _uuid.UUID(workspace_id)

    def _upsert(table: str, rows: list[dict]) -> None:
        if not rows:
            return
        data = json.dumps(rows).encode()
        req = urllib.request.Request(
            f"{url.rstrip('/')}/rest/v1/{table}",
            data=data,
            headers={
                "Content-Type": "application/json",
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Prefer": "resolution=merge-duplicates",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass

    def _serialize(row) -> dict:
        result = {}
        for col in row.__table__.columns:
            val = getattr(row, col.key, None)
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            elif not isinstance(val, (str, int, float, bool, type(None), dict, list)):
                val = str(val)
            result[col.key] = val
        return result

    from sqlalchemy import select

    from app.domain.ai import AiMultiAgentRun, AiToolProposal, ChatMessage, ChatSession
    from app.domain.ai_memory import AiMemory, AiMemorySuggestion

    memories = list(db.scalars(select(AiMemory).where(AiMemory.workspace_id == ws)).all())
    _upsert("ai_memories", [_serialize(m) for m in memories])

    suggestions = list(
        db.scalars(select(AiMemorySuggestion).where(AiMemorySuggestion.workspace_id == ws)).all()
    )
    _upsert("ai_memory_suggestions", [_serialize(s) for s in suggestions])

    sessions = list(
        db.scalars(select(ChatSession).where(ChatSession.workspace_id == ws)).all()
    )
    _upsert("chat_sessions", [_serialize(s) for s in sessions])

    messages = list(
        db.scalars(select(ChatMessage).where(ChatMessage.workspace_id == ws)).all()
    )
    _upsert("chat_messages", [_serialize(m) for m in messages])

    proposals = list(
        db.scalars(select(AiToolProposal).where(AiToolProposal.workspace_id == ws)).all()
    )
    _upsert("ai_tool_proposals", [_serialize(p) for p in proposals])

    runs = list(
        db.scalars(select(AiMultiAgentRun).where(AiMultiAgentRun.workspace_id == ws)).all()
    )
    _upsert("ai_multi_agent_runs", [_serialize(r) for r in runs])
