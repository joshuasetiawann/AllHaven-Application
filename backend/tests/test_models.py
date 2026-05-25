"""Model registration tests."""

from app.domain.base import Base

EXPECTED_TABLES = {
    "local_users",
    "profiles",
    "user_sessions",
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
}


def test_all_models_registered():
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables.keys()))


def test_expected_table_count():
    assert len(Base.metadata.tables) == len(EXPECTED_TABLES)
