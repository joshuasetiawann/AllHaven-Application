"""Domain layer: SQLAlchemy models.

Importing this package registers every model on ``Base.metadata`` so Alembic and
``create_all`` can see the full schema.
"""

from app.domain.ai import AiToolProposal, ChatMessage, ChatSession
from app.domain.audit import AuditLog
from app.domain.base import Base
from app.domain.finance import FinanceCategory, Transaction
from app.domain.notes import Note
from app.domain.tasks import Task
from app.domain.users import LocalUser, Profile
from app.domain.workspaces import Workspace, WorkspaceMember

__all__ = [
    "Base",
    "LocalUser",
    "Profile",
    "Workspace",
    "WorkspaceMember",
    "Task",
    "Note",
    "FinanceCategory",
    "Transaction",
    "ChatSession",
    "ChatMessage",
    "AiToolProposal",
    "AuditLog",
]
