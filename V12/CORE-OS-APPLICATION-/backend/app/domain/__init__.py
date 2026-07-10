"""Domain layer: SQLAlchemy models.

Importing this package registers every model on ``Base.metadata`` so Alembic and
``create_all`` can see the full schema.
"""

from app.domain.ai import (
    AiAgentResponse,
    AiMultiAgentRun,
    AiToolProposal,
    ChatMessage,
    ChatSession,
)
from app.domain.audit import AuditLog
from app.domain.automations import Automation
from app.domain.base import Base
from app.domain.calendar import CalendarEvent
from app.domain.files import DriveFile
from app.domain.finance import FinanceCategory, Transaction
from app.domain.integrations import AiAgentConfig, IntegrationConfig
from app.domain.notes import Note
from app.domain.tasks import Task, TaskChecklistItem
from app.domain.weather import WeatherLocation
from app.domain.users import LocalUser, Profile
from app.domain.workspaces import Workspace, WorkspaceMember

__all__ = [
    "Base",
    "LocalUser",
    "Profile",
    "Workspace",
    "WorkspaceMember",
    "Task",
    "TaskChecklistItem",
    "Note",
    "FinanceCategory",
    "Transaction",
    "ChatSession",
    "ChatMessage",
    "AiMultiAgentRun",
    "AiAgentResponse",
    "AiToolProposal",
    "AuditLog",
    "IntegrationConfig",
    "AiAgentConfig",
    "CalendarEvent",
    "DriveFile",
    "Automation",
    "WeatherLocation",
]
