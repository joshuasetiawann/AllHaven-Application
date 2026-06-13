"""Tests for AI memory tools in the tool registry.

Covers:
  - All 5 tools are registered with correct access/risk metadata
  - list_memories / search_memories return correct shapes and are workspace-scoped
  - create/update/delete handler end-to-end (direct execution + proposal flow)
  - Invalid/missing args raise ToolError (empty q, bad memory_id UUID)
  - update/delete of nonexistent or cross-workspace memory fail safely
"""

import uuid

import pytest

from app.core.principal import Principal
from app.services import ai_tools_registry, memory_service
from tests.conftest import API


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def _register_second_workspace(client):
    """Register a second user+workspace and return their principal."""
    resp = client.post(
        f"{API}/auth/register",
        json={
            "email": "other@example.com",
            "password": "password123",
            "full_name": "Other User",
        },
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    # Use an independent client for the second workspace
    from fastapi.testclient import TestClient
    from app.main import app
    other = TestClient(app)
    other.headers.update({"Authorization": f"Bearer {token}"})
    return other


# ---------------------------------------------------------------------------
# Tool registry metadata
# ---------------------------------------------------------------------------


def test_memory_tools_are_registered(auth_client, db_session):
    """All 5 memory tools appear in the registry with correct access/risk."""
    principal = _principal(auth_client)
    defs = {t["name"]: t for t in ai_tools_registry.list_tools_view(db_session, principal)}

    # Read tools
    for name in ("list_memories", "search_memories"):
        assert name in defs, f"{name} not found in registry"
        assert defs[name]["access"] == "read"
        assert defs[name]["risk"] == "LOW"
        assert defs[name]["module"] == "memory"
        assert defs[name]["approval_required"] is False

    # Write tools
    assert defs["create_memory"]["access"] == "write"
    assert defs["create_memory"]["risk"] == "LOW"
    assert defs["create_memory"]["approval_required"] is False

    assert defs["update_memory"]["access"] == "write"
    assert defs["update_memory"]["risk"] == "LOW"
    assert defs["update_memory"]["approval_required"] is False

    assert defs["delete_memory"]["access"] == "write"
    assert defs["delete_memory"]["risk"] == "MEDIUM"
    assert defs["delete_memory"]["approval_required"] is True


def test_memory_module_in_tool_list_endpoint(auth_client):
    """The /ai/tools endpoint includes memory tools in its module set."""
    data = auth_client.get(f"{API}/ai/tools").json()["data"]
    modules = {t["module"] for t in data}
    assert "memory" in modules


# ---------------------------------------------------------------------------
# list_memories
# ---------------------------------------------------------------------------


def test_list_memories_empty(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "list_memories", {})
    assert outcome["status"] == "executed"
    result = outcome["result"]
    assert result["memories"] == []
    assert result["count"] == 0


def test_list_memories_returns_seeded_rows(auth_client, db_session):
    principal = _principal(auth_client)
    memory_service.create_memory(
        db_session, principal, category="Profile", title="Name", content="Joshua"
    )
    memory_service.create_memory(
        db_session, principal, category="Technical", title="Lang", content="Python"
    )
    db_session.flush()

    outcome = ai_tools_registry.run_tool_call(db_session, principal, "list_memories", {})
    assert outcome["status"] == "executed"
    result = outcome["result"]
    assert result["count"] == 2
    titles = {m["title"] for m in result["memories"]}
    assert {"Name", "Lang"} == titles


def test_list_memories_by_category(auth_client, db_session):
    principal = _principal(auth_client)
    memory_service.create_memory(db_session, principal, category="Profile", title="Name", content="Joshua")
    memory_service.create_memory(db_session, principal, category="Technical", title="Lang", content="Python")
    db_session.flush()

    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "list_memories", {"category": "Profile"}
    )
    assert outcome["status"] == "executed"
    assert outcome["result"]["count"] == 1
    assert outcome["result"]["memories"][0]["category"] == "Profile"


def test_list_memories_workspace_scoped(auth_client, db_session, client):
    """Memories from another workspace must NOT appear in list_memories."""
    principal = _principal(auth_client)

    # Seed a memory for the first workspace
    memory_service.create_memory(
        db_session, principal, category="Profile", title="MyName", content="Joshua"
    )
    db_session.flush()

    # Register a second workspace and seed a memory there
    other_client = _register_second_workspace(client)
    other_me = other_client.get(f"{API}/auth/me").json()["data"]
    other_principal = Principal(
        user_id=uuid.UUID(other_me["user"]["id"]),
        workspace_id=uuid.UUID(other_me["workspace"]["id"]),
        email=other_me["user"]["email"],
    )
    memory_service.create_memory(
        db_session, other_principal, category="Profile", title="OtherName", content="Alice"
    )
    db_session.flush()

    # The first principal must only see its own memory
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "list_memories", {})
    assert outcome["status"] == "executed"
    titles = {m["title"] for m in outcome["result"]["memories"]}
    assert "MyName" in titles
    assert "OtherName" not in titles


# ---------------------------------------------------------------------------
# search_memories
# ---------------------------------------------------------------------------


def test_search_memories_finds_match(auth_client, db_session):
    principal = _principal(auth_client)
    memory_service.create_memory(
        db_session, principal, category="Technical", title="Favorite language", content="Uses Python daily"
    )
    db_session.flush()

    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "search_memories", {"q": "Python"}
    )
    assert outcome["status"] == "executed"
    assert outcome["result"]["count"] == 1
    assert outcome["result"]["memories"][0]["title"] == "Favorite language"


def test_search_memories_no_results(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "search_memories", {"q": "nonexistent_term_xyz"}
    )
    assert outcome["status"] == "executed"
    assert outcome["result"]["count"] == 0


def test_search_memories_empty_q_raises_error(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "search_memories", {"q": ""}
    )
    assert outcome["status"] == "error"
    assert "search query" in outcome["error"].lower() or "q" in outcome["error"]


def test_search_memories_missing_q_raises_error(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "search_memories", {}
    )
    assert outcome["status"] == "error"


def test_search_memories_workspace_scoped(auth_client, db_session, client):
    """Search must not leak memories from another workspace."""
    principal = _principal(auth_client)
    memory_service.create_memory(
        db_session, principal, category="Profile", title="My note", content="secret value alpha"
    )
    db_session.flush()

    other_client = _register_second_workspace(client)
    other_me = other_client.get(f"{API}/auth/me").json()["data"]
    other_principal = Principal(
        user_id=uuid.UUID(other_me["user"]["id"]),
        workspace_id=uuid.UUID(other_me["workspace"]["id"]),
        email=other_me["user"]["email"],
    )
    # Other workspace searching for the same content must get 0 results
    outcome = ai_tools_registry.run_tool_call(
        db_session, other_principal, "search_memories", {"q": "alpha"}
    )
    assert outcome["status"] == "executed"
    assert outcome["result"]["count"] == 0


# ---------------------------------------------------------------------------
# create_memory (low-risk write tool - executes directly)
# ---------------------------------------------------------------------------


def test_create_memory_executes_directly(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "create_memory",
        {"category": "Profile", "title": "Nickname", "content": "Goes by Josh"}
    )
    db_session.commit()
    assert outcome["status"] == "executed"
    assert outcome["result"]["memory"]["title"] == "Nickname"

    memories = memory_service.list_memories(db_session, principal)
    assert any(m.title == "Nickname" for m in memories)


def test_create_memory_direct_result_shape(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "create_memory",
        {"category": "Preferences", "title": "Theme", "content": "Prefers dark mode"}
    )
    db_session.commit()

    assert outcome["status"] == "executed"
    assert outcome["result"]["memory"]["title"] == "Theme"
    assert outcome["result"]["memory"]["category"] == "Preferences"

    # Memory now exists
    memories = memory_service.list_memories(db_session, principal)
    assert any(m.title == "Theme" for m in memories)


def test_create_memory_auto_executes_when_approval_off(auth_client, db_session):
    """With require_approval=False, LOW-risk write executes directly."""
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": False})
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "create_memory",
        {"category": "Goals", "title": "Run a marathon", "content": "Wants to run a marathon in 2027"}
    )
    db_session.commit()
    assert outcome["status"] == "executed"
    memories = memory_service.list_memories(db_session, principal)
    assert any(m.title == "Run a marathon" for m in memories)
    # Restore default
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": True})


# ---------------------------------------------------------------------------
# update_memory (write tool)
# ---------------------------------------------------------------------------


def test_update_memory_executes_directly(auth_client, db_session):
    principal = _principal(auth_client)
    # Create memory directly (bypassing tool for setup)
    m = memory_service.create_memory(
        db_session, principal, category="Profile", title="City", content="Lives in Jakarta"
    )
    db_session.flush()

    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "update_memory",
        {"memory_id": str(m.id), "title": "City", "content": "Lives in Bandung"}
    )
    db_session.commit()
    assert outcome["status"] == "executed"
    result = outcome["result"]["memory"]
    assert result["content"] == "Lives in Bandung"


def test_update_memory_invalid_uuid(auth_client, db_session):
    principal = _principal(auth_client)
    # With approval required, invalid UUID goes into proposal args; the error
    # surfaces when the proposal is approved (or during auto-execute).
    # With approval off, the error is immediate.
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": False})
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "update_memory",
        {"memory_id": "not-a-uuid", "content": "New content"}
    )
    db_session.commit()
    assert outcome["status"] == "error"
    assert "memory_id" in outcome["error"]
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": True})


def test_update_memory_nonexistent_id(auth_client, db_session):
    principal = _principal(auth_client)
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": False})
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "update_memory",
        {"memory_id": str(uuid.uuid4()), "content": "Ghost update"}
    )
    db_session.commit()
    assert outcome["status"] == "error"
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": True})


def test_update_memory_cross_workspace_denied(auth_client, db_session, client):
    """Cannot update a memory belonging to another workspace."""
    principal = _principal(auth_client)

    other_client = _register_second_workspace(client)
    other_me = other_client.get(f"{API}/auth/me").json()["data"]
    other_principal = Principal(
        user_id=uuid.UUID(other_me["user"]["id"]),
        workspace_id=uuid.UUID(other_me["workspace"]["id"]),
        email=other_me["user"]["email"],
    )
    # Create memory in the OTHER workspace
    m = memory_service.create_memory(
        db_session, other_principal, category="Profile", title="Secret", content="Top secret"
    )
    db_session.flush()

    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": False})
    # First principal tries to update the other workspace's memory
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "update_memory",
        {"memory_id": str(m.id), "content": "Hacked!"}
    )
    db_session.commit()
    assert outcome["status"] == "error"
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": True})


# ---------------------------------------------------------------------------
# delete_memory (write tool — MEDIUM risk)
# ---------------------------------------------------------------------------


def test_delete_memory_via_proposal(auth_client, db_session):
    principal = _principal(auth_client)
    m = memory_service.create_memory(
        db_session, principal, category="Profile", title="ToDelete", content="Will be deleted"
    )
    db_session.flush()

    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "delete_memory", {"memory_id": str(m.id)}
    )
    db_session.commit()
    assert outcome["status"] == "pending_approval"

    resp = auth_client.post(f"{API}/ai/proposals/{outcome['proposal_id']}/approve")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["result"]["deleted"] is True

    # Memory no longer exists
    memories = memory_service.list_memories(db_session, principal)
    assert all(x.title != "ToDelete" for x in memories)


def test_delete_memory_invalid_uuid(auth_client, db_session):
    principal = _principal(auth_client)
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": False})
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "delete_memory", {"memory_id": "bad-id"}
    )
    db_session.commit()
    assert outcome["status"] == "error"
    assert "memory_id" in outcome["error"]
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": True})


def test_delete_memory_nonexistent_id(auth_client, db_session):
    principal = _principal(auth_client)
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": False})
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "delete_memory", {"memory_id": str(uuid.uuid4())}
    )
    db_session.commit()
    assert outcome["status"] == "error"
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": True})


def test_delete_memory_cross_workspace_denied(auth_client, db_session, client):
    """Cannot delete a memory belonging to another workspace."""
    principal = _principal(auth_client)

    other_client = _register_second_workspace(client)
    other_me = other_client.get(f"{API}/auth/me").json()["data"]
    other_principal = Principal(
        user_id=uuid.UUID(other_me["user"]["id"]),
        workspace_id=uuid.UUID(other_me["workspace"]["id"]),
        email=other_me["user"]["email"],
    )
    m = memory_service.create_memory(
        db_session, other_principal, category="Profile", title="OtherSecret", content="private"
    )
    db_session.flush()

    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": False})
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "delete_memory", {"memory_id": str(m.id)}
    )
    db_session.commit()
    assert outcome["status"] == "error"
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": True})


# ---------------------------------------------------------------------------
# create_memory input validation (handler runs only when approval is OFF)
# ---------------------------------------------------------------------------
# The registry's write path with require_approval=ON stores a PENDING proposal
# without ever calling the handler, so validation in the handler never fires.
# These tests disable approval so the handler executes immediately.


def test_create_memory_blank_title_raises_error(auth_client, db_session):
    """Blank title must produce a ToolError, not a silent empty-string memory."""
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": False})
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "create_memory",
        {"category": "Profile", "title": "   ", "content": "Some content"}
    )
    db_session.commit()
    assert outcome["status"] == "error"
    assert "title" in outcome["error"].lower()
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": True})


def test_create_memory_blank_content_raises_error(auth_client, db_session):
    """Blank content must produce a ToolError."""
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": False})
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "create_memory",
        {"category": "Profile", "title": "My title", "content": ""}
    )
    db_session.commit()
    assert outcome["status"] == "error"
    assert "content" in outcome["error"].lower()
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": True})


def test_create_memory_invalid_category_raises_error(auth_client, db_session):
    """An unrecognised category must produce a ToolError listing valid values."""
    from app.domain.ai_memory import MEMORY_CATEGORIES

    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": False})
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "create_memory",
        {"category": "Hobbies", "title": "My title", "content": "Some content"}
    )
    db_session.commit()
    assert outcome["status"] == "error"
    error_text = outcome["error"]
    # Error must mention the invalid value and at least one valid category
    assert "Hobbies" in error_text or "category" in error_text.lower()
    assert any(cat in error_text for cat in MEMORY_CATEGORIES)
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": True})


def test_create_memory_missing_category_defaults_to_profile(auth_client, db_session):
    """Omitting category should default to 'Profile' and succeed."""
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": False})
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "create_memory",
        {"title": "Default cat test", "content": "No category supplied"}
    )
    db_session.commit()
    assert outcome["status"] == "executed", outcome.get("error")
    assert outcome["result"]["memory"]["category"] == "Profile"
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": True})


# ---------------------------------------------------------------------------
# Memory result shape validation
# ---------------------------------------------------------------------------


def test_list_memories_result_has_required_fields(auth_client, db_session):
    principal = _principal(auth_client)
    memory_service.create_memory(
        db_session, principal, category="Profile", title="Bio", content="Software developer"
    )
    db_session.flush()

    outcome = ai_tools_registry.run_tool_call(db_session, principal, "list_memories", {})
    m = outcome["result"]["memories"][0]
    assert all(k in m for k in ("id", "category", "title", "content", "source"))


def test_search_memories_result_has_required_fields(auth_client, db_session):
    principal = _principal(auth_client)
    memory_service.create_memory(
        db_session, principal, category="Technical", title="Stack", content="FastAPI + React"
    )
    db_session.flush()

    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "search_memories", {"q": "FastAPI"}
    )
    m = outcome["result"]["memories"][0]
    assert all(k in m for k in ("id", "category", "title", "content"))
