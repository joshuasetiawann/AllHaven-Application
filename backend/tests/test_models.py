"""Model registration and referential-integrity tests."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.base import Base
from app.domain.tasks import Task, TaskChecklistItem
from app.domain.users import LocalUser, Profile
from app.domain.workspaces import Workspace

EXPECTED_TABLES = {
    "local_users",
    "profiles",
    "user_sessions",
    "bearer_token_revocations",
    "workspaces",
    "workspace_members",
    "tasks",
    "notes",
    "finance_categories",
    "transactions",
    "chat_groups",
    "chat_sessions",
    "chat_messages",
    "ai_multi_agent_runs",
    "ai_agent_responses",
    "ai_tool_proposals",
    "ai_tool_calls",
    "audit_logs",
    "integration_configs",
    "ai_agent_configs",
    "task_checklist_items",
    "calendar_events",
    "drive_files",
    "automations",
    "weather_locations",
    "ai_memories",
    "ai_memory_suggestions",
    "ai_conversation_summaries",
    "ai_knowledge_documents",
    "ai_knowledge_chunks",
    "sync_state",
}


def test_all_models_registered():
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables.keys()))


def test_expected_table_count():
    assert len(Base.metadata.tables) == len(EXPECTED_TABLES)


def test_core_relationships_are_enforced_by_foreign_keys():
    """Every concrete UUID ownership/parent link has a database constraint."""
    expected = {
        ("workspaces", "owner_id", "profiles.id", "RESTRICT"),
        ("workspace_members", "workspace_id", "workspaces.id", "CASCADE"),
        ("workspace_members", "user_id", "profiles.id", "CASCADE"),
        ("user_sessions", "user_id", "local_users.id", "CASCADE"),
        ("tasks", "workspace_id", "workspaces.id", "CASCADE"),
        ("task_checklist_items", "task_id", "tasks.id", "CASCADE"),
        ("transactions", "category_id", "finance_categories.id", "SET NULL"),
        ("chat_sessions", "group_id", "chat_groups.id", "SET NULL"),
        ("chat_messages", "session_id", "chat_sessions.id", "CASCADE"),
        ("ai_agent_responses", "run_id", "ai_multi_agent_runs.id", "CASCADE"),
        ("ai_knowledge_chunks", "document_id", "ai_knowledge_documents.id", "CASCADE"),
    }
    actual = {
        (table.name, fk.parent.name, fk.target_fullname, fk.ondelete)
        for table in Base.metadata.tables.values()
        for fk in table.foreign_keys
    }
    assert expected <= actual
    # The audit baseline had only one FK. Keep a broad inventory regression so
    # future model edits cannot silently return ownership to app-only checks.
    assert len(actual) >= 60


def test_tenant_local_parent_links_use_composite_foreign_keys():
    expected = {
        ("task_checklist_items", ("workspace_id", "task_id"), "tasks"),
        ("transactions", ("workspace_id", "category_id"), "finance_categories"),
        ("chat_sessions", ("workspace_id", "group_id"), "chat_groups"),
        ("chat_messages", ("workspace_id", "session_id"), "chat_sessions"),
        ("ai_agent_responses", ("workspace_id", "run_id"), "ai_multi_agent_runs"),
        (
            "ai_knowledge_chunks",
            ("workspace_id", "document_id"),
            "ai_knowledge_documents",
        ),
    }
    actual = {
        (
            table.name,
            tuple(element.parent.name for element in constraint.elements),
            constraint.referred_table.name,
        )
        for table in Base.metadata.tables.values()
        for constraint in table.foreign_key_constraints
        if len(constraint.elements) == 2
    }
    assert expected <= actual


def test_cross_workspace_checklist_reference_is_rejected(db_session):
    """A child cannot claim workspace B while pointing at a task in A."""
    user_a = Profile(id=uuid.uuid4(), email="tenant-a@example.com")
    user_b = Profile(id=uuid.uuid4(), email="tenant-b@example.com")
    workspace_a = Workspace(id=uuid.uuid4(), name="A", owner_id=user_a.id)
    workspace_b = Workspace(id=uuid.uuid4(), name="B", owner_id=user_b.id)
    task = Task(
        id=uuid.uuid4(), workspace_id=workspace_a.id, created_by=user_a.id, title="private"
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()
    db_session.add_all([workspace_a, workspace_b])
    db_session.commit()
    db_session.add(task)
    db_session.commit()

    db_session.add(
        TaskChecklistItem(
            id=uuid.uuid4(),
            workspace_id=workspace_b.id,
            created_by=user_b.id,
            task_id=task.id,
            title="injected",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_identity_email_indexes_are_case_insensitive(db_session):
    db_session.add(LocalUser(email="Mixed@Example.com", hashed_password="x"))
    db_session.commit()
    db_session.add(LocalUser(email="mixed@example.COM", hashed_password="y"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(Profile(email="Profile@Example.com"))
    db_session.commit()
    db_session.add(Profile(email="profile@EXAMPLE.com"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
