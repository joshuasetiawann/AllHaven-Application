# backend/app/services/sync_registry.py
"""Sync registry — derives the synced-table list from ORM models.

``SYNCED_TABLES`` is the single source of truth for which tables participate in
the two-way desktop-Postgres ⇄ Supabase sync, in FK-safe apply order
(parents before children). ``sync_state``, ``local_users``, and
``user_sessions`` are intentionally excluded.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Import models — paths verified against backend/app/domain/__init__.py
# ---------------------------------------------------------------------------
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


@dataclass(frozen=True)
class SyncSpec:
    """Describes how one table participates in the two-way sync."""

    model: type
    table_name: str
    watermark_col: str = "updated_at"
    append_only: bool = False
    user_scoped: bool = False  # scope by Profile.id ∈ members instead of workspace_id

    def scope(self, ws: uuid.UUID, member_ids: list[uuid.UUID]):
        """Return a SQLAlchemy filter expression for this table scoped to *ws*."""
        if self.table_name == "workspaces":
            return self.model.id == ws
        if self.user_scoped:  # profiles
            return self.model.id.in_(member_ids or [uuid.uuid4()])
        return self.model.workspace_id == ws


def _spec(model, watermark: str = "updated_at", append_only: bool = False, user_scoped: bool = False) -> SyncSpec:
    return SyncSpec(model, model.__tablename__, watermark, append_only, user_scoped)


# Parents before children (FK-safe apply order).
# Excluded: sync_state (local bookkeeping), local_users, user_sessions (auth/secret).
SYNCED_TABLES: list[SyncSpec] = [
    _spec(Workspace),
    _spec(WorkspaceMember),
    _spec(Profile, user_scoped=True),
    _spec(Task),
    _spec(TaskChecklistItem),
    _spec(Note),
    _spec(FinanceCategory),
    _spec(Transaction),
    _spec(CalendarEvent),
    _spec(DriveFile),
    _spec(Automation),
    _spec(WeatherLocation),
    _spec(IntegrationConfig),
    _spec(AiAgentConfig),
    _spec(ChatGroup),
    _spec(ChatSession),
    _spec(ChatMessage, watermark="created_at", append_only=True),
    _spec(AiToolProposal, watermark="created_at", append_only=True),
    _spec(AiToolCall, watermark="created_at", append_only=True),
    _spec(AiMultiAgentRun),
    _spec(AiAgentResponse, watermark="created_at", append_only=True),
    _spec(AiMemory),
    _spec(AiMemorySuggestion, watermark="created_at", append_only=True),
    _spec(AiConversationSummary),
    _spec(AiKnowledgeDocument),
    _spec(AiKnowledgeChunk, watermark="created_at", append_only=True),
    _spec(AuditLog, watermark="created_at", append_only=True),
]

_BY_NAME: dict[str, SyncSpec] = {s.table_name: s for s in SYNCED_TABLES}


def spec_for(table_name: str) -> SyncSpec | None:
    """Return the ``SyncSpec`` for *table_name*, or ``None`` if not registered."""
    return _BY_NAME.get(table_name)
