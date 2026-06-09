"""Tests for the AI Tool Registry, human approval flow, chat settings, and model slots.

Covers the security core: tool allowlisting, read-vs-write behavior (writes never
execute without approval), HIGH-risk always needing approval, approve/reject/edit,
and the audit trail's honesty (a pending action is pending, not done).
"""

import uuid

from app.core.principal import Principal
from app.services import ai_tools_registry
from tests.conftest import API


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


# --- registry surface (API) -------------------------------------------------


def test_tools_endpoint_lists_registry(auth_client):
    data = auth_client.get(f"{API}/ai/tools").json()["data"]
    by_name = {t["name"]: t for t in data}
    assert "list_tasks" in by_name and by_name["list_tasks"]["access"] == "read"
    assert by_name["create_task"]["access"] == "write"
    assert by_name["create_task"]["approval_required"] is True
    assert by_name["restart_service"]["risk"] == "HIGH"
    assert all(t["enabled"] for t in data)  # everything enabled by default
    # Modules span the whole app.
    modules = {t["module"] for t in data}
    assert {"time", "tasks", "calendar", "notes", "finance", "files",
            "weather", "automation", "system"}.issubset(modules)


def test_tool_disable_enable(auth_client):
    resp = auth_client.put(f"{API}/ai/tools/list_tasks", json={"enabled": False})
    assert resp.status_code == 200 and resp.json()["data"]["enabled"] is False
    data = auth_client.get(f"{API}/ai/tools").json()["data"]
    assert next(t for t in data if t["name"] == "list_tasks")["enabled"] is False
    # Unknown tool name is rejected (allowlist).
    assert auth_client.put(f"{API}/ai/tools/run_anything", json={"enabled": True}).status_code == 404
    auth_client.put(f"{API}/ai/tools/list_tasks", json={"enabled": True})


# --- chat behavior settings (API) --------------------------------------------


def test_chat_settings_defaults_and_update(auth_client):
    data = auth_client.get(f"{API}/ai/settings/chat").json()["data"]
    assert data["require_approval"] is True       # safety default ON
    assert data["show_debate_flow"] is True       # preserves existing behavior
    assert data["max_active_agents"] == 10

    resp = auth_client.put(
        f"{API}/ai/settings/chat",
        json={"show_debate_flow": False, "max_active_agents": 5, "default_mode": "debate"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["show_debate_flow"] is False and data["max_active_agents"] == 5
    assert data["default_mode"] == "debate"

    # Validation: bad values rejected.
    assert auth_client.put(f"{API}/ai/settings/chat", json={"default_mode": "anarchy"}).status_code == 422
    assert auth_client.put(f"{API}/ai/settings/chat", json={"max_active_agents": 11}).status_code == 422


# --- model slots (API) --------------------------------------------------------


def test_model_slots_update(auth_client):
    resp = auth_client.put(
        f"{API}/ai/providers/anthropic/slots",
        json={"slots": [{"slot": 2, "model": "claude-3-5-haiku-latest", "role": "Critic / Risk"}]},
    )
    assert resp.status_code == 200, resp.text
    slots = resp.json()["data"]["model_slots"]
    assert slots[1]["configured"] is True
    assert slots[1]["model"] == "claude-3-5-haiku-latest"
    assert slots[1]["role"] == "Critic / Risk"
    assert slots[1]["ref"] == "anthropic#2"
    # OpenRouter agents are single-slot: slot 2 is rejected.
    resp = auth_client.put(
        f"{API}/ai/providers/openrouter_1/slots",
        json={"slots": [{"slot": 2, "model": "x"}]},
    )
    assert resp.status_code == 422


# --- tool execution policy (service level) ------------------------------------


def test_read_tool_executes_immediately(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "get_current_time", {})
    assert outcome["status"] == "executed"
    assert "iso" in outcome["result"] and "timezone" in outcome["result"]


def test_unknown_tool_is_rejected(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "run_shell", {"cmd": "rm -rf /"})
    assert outcome["status"] == "error"
    assert "Unknown tool" in outcome["error"]


def test_write_tool_creates_pending_proposal_not_data(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "create_task", {"title": "Buy milk", "priority": "HIGH"}
    )
    db_session.commit()
    assert outcome["status"] == "pending_approval"
    assert outcome["proposal_id"]
    assert "NOT been executed" in outcome["note"]
    # The task was NOT created…
    tasks = auth_client.get(f"{API}/tasks").json()["data"]
    assert all(t["title"] != "Buy milk" for t in tasks)
    # …but the proposal is visible as pending.
    proposals = auth_client.get(f"{API}/ai/proposals").json()["data"]
    assert any(p["id"] == outcome["proposal_id"] for p in proposals)


def test_approve_executes_the_action(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "create_task", {"title": "Ship v0.12"})
    db_session.commit()
    resp = auth_client.post(f"{API}/ai/proposals/{outcome['proposal_id']}/approve")
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["proposal"]["status"] == "EXECUTED"
    assert body["result"]["task"]["title"] == "Ship v0.12"
    # The task now exists, and the proposal left the pending list.
    tasks = auth_client.get(f"{API}/tasks").json()["data"]
    assert any(t["title"] == "Ship v0.12" for t in tasks)
    pending = auth_client.get(f"{API}/ai/proposals").json()["data"]
    assert all(p["id"] != outcome["proposal_id"] for p in pending)
    # Double-approve is rejected honestly.
    assert auth_client.post(f"{API}/ai/proposals/{outcome['proposal_id']}/approve").status_code == 422


def test_reject_does_nothing(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "create_task", {"title": "Never created"})
    db_session.commit()
    resp = auth_client.post(f"{API}/ai/proposals/{outcome['proposal_id']}/reject")
    assert resp.status_code == 200
    tasks = auth_client.get(f"{API}/tasks").json()["data"]
    assert all(t["title"] != "Never created" for t in tasks)


def test_edit_then_approve_uses_edited_payload(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "create_task", {"title": "Old title"})
    db_session.commit()
    pid = outcome["proposal_id"]
    resp = auth_client.patch(f"{API}/ai/proposals/{pid}", json={"tool_payload": {"title": "Edited title"}})
    assert resp.status_code == 200
    resp = auth_client.post(f"{API}/ai/proposals/{pid}/approve")
    assert resp.status_code == 200
    assert resp.json()["data"]["result"]["task"]["title"] == "Edited title"


def test_high_risk_requires_approval_even_when_approval_off(auth_client, db_session):
    principal = _principal(auth_client)
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": False})
    # LOW-risk write executes directly when the workspace opts out of approvals…
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "create_task", {"title": "Auto task"})
    db_session.commit()
    assert outcome["status"] == "executed"
    # …but HIGH-risk actions STILL require human approval.
    outcome = ai_tools_registry.run_tool_call(
        db_session, principal, "delete_file", {"file_id": str(uuid.uuid4())}
    )
    db_session.commit()
    assert outcome["status"] == "pending_approval"
    auth_client.put(f"{API}/ai/settings/chat", json={"require_approval": True})


def test_disabled_tool_cannot_run(auth_client, db_session):
    principal = _principal(auth_client)
    auth_client.put(f"{API}/ai/tools/get_current_time", json={"enabled": False})
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "get_current_time", {})
    assert outcome["status"] == "error" and "disabled" in outcome["error"]
    auth_client.put(f"{API}/ai/tools/get_current_time", json={"enabled": True})


def test_approve_with_invalid_payload_fails_honestly(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "create_task", {})  # missing title
    db_session.commit()
    resp = auth_client.post(f"{API}/ai/proposals/{outcome['proposal_id']}/approve")
    assert resp.status_code == 422
    assert "execution failed" in resp.json()["message"].lower()


def test_tool_definitions_export_openai_format(auth_client, db_session):
    principal = _principal(auth_client)
    defs = ai_tools_registry.tool_definitions(db_session, principal)
    assert all(d["type"] == "function" for d in defs)
    create = next(d for d in defs if d["function"]["name"] == "create_task")
    assert create["function"]["parameters"]["required"] == ["title"]
    assert create["function"]["parameters"]["additionalProperties"] is False
