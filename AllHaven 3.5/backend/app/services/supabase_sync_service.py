# backend/app/services/supabase_sync_service.py
"""Optional Supabase sync — runs in background, never blocks main flow.

Enabled by configuring SUPABASE_URL and SUPABASE_ANON_KEY via Settings → Integrations.
Sync direction: local PostgreSQL → Supabase (one-way mirror for now).
All sync errors are silently logged — never raised to callers.

Security:
- The anon key is NEVER logged.
- The anon key is NEVER included in returned messages.
- This module never raises to its callers.
- Auth password hashes and browser session token hashes are intentionally not
  mirrored. Workspace/product data is local-first; Supabase is an optional copy.
  Integration/provider secrets are mirrored only as already-encrypted DB blobs.
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

    Returns ``{"status": "not_configured", ...}`` when credentials are missing or
    the URL scheme is not http:// or https://.
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

    if not url.startswith(("http://", "https://")):
        return {
            "status": "not_configured",
            "message": "Supabase URL must start with http:// or https://.",
        }

    workspace_id = str(principal.workspace_id)
    t = threading.Thread(
        target=_sync_thread, args=(url, key, workspace_id), daemon=True
    )
    t.start()
    return {"status": "syncing", "message": "Background sync started."}


def sync_if_configured(db: Session, principal: Principal) -> dict:
    """Fire-and-forget sync helper for routers after a successful local write.

    The local database remains the source of truth. This helper deliberately
    returns a normal status object and never raises, so write endpoints stay fast
    and reliable even when Supabase is offline or not configured.
    """
    try:
        return sync_all(db, principal)
    except Exception as exc:
        log.debug("Supabase auto-sync trigger failed: %s", exc)
        return {"status": "error", "message": "Supabase sync could not be started."}


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
    """Attempt to sync workspace tables to Supabase using REST (no SDK required).

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
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass

    def _serialize(row) -> dict:
        import sqlalchemy

        result = {}
        for attr in sqlalchemy.inspect(row).mapper.column_attrs:
            col_name = attr.columns[0].name  # actual DB column name (e.g. "metadata")
            val = getattr(row, attr.key)      # Python attribute name (e.g. "meta")
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            elif not isinstance(val, (str, int, float, bool, type(None), dict, list)):
                val = str(val)
            result[col_name] = val
        return result

    from sqlalchemy import select

    from app.domain.ai import (
        AiAgentResponse,
        AiMultiAgentRun,
        AiToolCall,
        AiToolProposal,
        ChatGroup,
        ChatMessage,
        ChatSession,
    )
    from app.domain.ai_knowledge import AiKnowledgeChunk, AiKnowledgeDocument
    from app.domain.ai_memory import AiConversationSummary, AiMemory, AiMemorySuggestion
    from app.domain.audit import AuditLog
    from app.domain.automations import Automation
    from app.domain.calendar import CalendarEvent
    from app.domain.files import DriveFile
    from app.domain.finance import FinanceCategory, Transaction
    from app.domain.integrations import AiAgentConfig, IntegrationConfig
    from app.domain.notes import Note
    from app.domain.tasks import Task, TaskChecklistItem
    from app.domain.users import Profile
    from app.domain.weather import WeatherLocation
    from app.domain.workspaces import Workspace, WorkspaceMember

    workspace_tables = [
        (Workspace, Workspace.id == ws),
        (WorkspaceMember, WorkspaceMember.workspace_id == ws),
        (Task, Task.workspace_id == ws),
        (TaskChecklistItem, TaskChecklistItem.workspace_id == ws),
        (Note, Note.workspace_id == ws),
        (FinanceCategory, FinanceCategory.workspace_id == ws),
        (Transaction, Transaction.workspace_id == ws),
        (CalendarEvent, CalendarEvent.workspace_id == ws),
        (DriveFile, DriveFile.workspace_id == ws),
        (Automation, Automation.workspace_id == ws),
        (WeatherLocation, WeatherLocation.workspace_id == ws),
        (IntegrationConfig, IntegrationConfig.workspace_id == ws),
        (AiAgentConfig, AiAgentConfig.workspace_id == ws),
        (ChatGroup, ChatGroup.workspace_id == ws),
        (ChatSession, ChatSession.workspace_id == ws),
        (ChatMessage, ChatMessage.workspace_id == ws),
        (AiToolProposal, AiToolProposal.workspace_id == ws),
        (AiToolCall, AiToolCall.workspace_id == ws),
        (AiMultiAgentRun, AiMultiAgentRun.workspace_id == ws),
        (AiAgentResponse, AiAgentResponse.workspace_id == ws),
        (AiMemory, AiMemory.workspace_id == ws),
        (AiMemorySuggestion, AiMemorySuggestion.workspace_id == ws),
        (AiConversationSummary, AiConversationSummary.workspace_id == ws),
        (AiKnowledgeDocument, AiKnowledgeDocument.workspace_id == ws),
        (AiKnowledgeChunk, AiKnowledgeChunk.workspace_id == ws),
        (AuditLog, AuditLog.workspace_id == ws),
    ]

    # Public profile rows are user-scoped rather than workspace-scoped. Mirror
    # only profiles that belong to this workspace membership.
    member_user_ids = [
        row.user_id for row in db.scalars(
            select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws)
        ).all()
    ]
    if member_user_ids:
        workspace_tables.append((Profile, Profile.id.in_(member_user_ids)))

    for model, clause in workspace_tables:
        rows = list(db.scalars(select(model).where(clause)).all())
        try:
            _upsert(model.__tablename__, [_serialize(row) for row in rows])
        except Exception as exc:
            # Supabase may not have every table yet. Keep the local app working
            # and continue mirroring the remaining tables.
            log.debug("Supabase table sync skipped for %s: %s", model.__tablename__, exc)
