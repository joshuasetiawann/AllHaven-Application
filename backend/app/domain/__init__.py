"""Domain layer: SQLAlchemy models.

Importing this package registers every model on ``Base.metadata`` so Alembic and
``create_all`` can see the full schema.
"""

from app.domain.ai import (
    AiAgentResponse,
    AiMultiAgentRun,
    AiToolCall,
    AiToolProposal,
    ChatGroup,
    ChatMessage,
    ChatSession,
)
from app.domain.ai_memory import AiMemory, AiMemorySuggestion, AiConversationSummary
from app.domain.ai_knowledge import AiKnowledgeChunk, AiKnowledgeDocument
from app.domain.audit import AuditLog
from app.domain.automations import Automation
from app.domain.base import Base
from app.domain.calendar import CalendarEvent
from app.domain.files import DriveFile
from app.domain.finance import FinanceCategory, Transaction
from app.domain.integrations import AiAgentConfig, IntegrationConfig
from app.domain.notes import Note
from app.domain.sessions import UserSession
from app.domain.tasks import Task, TaskChecklistItem
from app.domain.weather import WeatherLocation
from app.domain.users import LocalUser, Profile
from app.domain.workspaces import Workspace, WorkspaceMember
from app.domain.sync_state import SyncState  # noqa: F401

__all__ = [
    "Base",
    "LocalUser",
    "UserSession",
    "Profile",
    "Workspace",
    "WorkspaceMember",
    "Task",
    "TaskChecklistItem",
    "Note",
    "FinanceCategory",
    "Transaction",
    "ChatGroup",
    "ChatSession",
    "ChatMessage",
    "AiMultiAgentRun",
    "AiAgentResponse",
    "AiToolCall",
    "AiToolProposal",
    "AiKnowledgeDocument",
    "AiKnowledgeChunk",
    "AuditLog",
    "IntegrationConfig",
    "AiAgentConfig",
    "CalendarEvent",
    "DriveFile",
    "Automation",
    "WeatherLocation",
    "AiMemory",
    "AiMemorySuggestion",
    "AiConversationSummary",
    "SyncState",
]
