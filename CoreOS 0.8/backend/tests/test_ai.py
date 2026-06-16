"""AI foundation tests: honest chat, sessions, and proposal rejection."""

import uuid

from app.domain.ai import AiToolProposal
from tests.conftest import API


def test_chat_is_honest_when_not_configured(auth_client):
    resp = auth_client.post(f"{API}/ai/chat", json={"message": "Hello there"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # No fake AI: assistant reports it is not configured.
    assert data["ai_configured"] is False
    assert data["reply"]["role"] == "assistant"
    assert "not configured" in data["reply"]["content"].lower()
    session_id = data["session_id"]

    # The session and both messages are persisted.
    messages = auth_client.get(f"{API}/ai/sessions/{session_id}/messages")
    assert len(messages.json()["data"]) == 2

    sessions = auth_client.get(f"{API}/ai/sessions")
    assert len(sessions.json()["data"]) == 1


def test_proposals_empty_and_reject_unknown_404(auth_client):
    assert auth_client.get(f"{API}/ai/proposals").json()["data"] == []
    resp = auth_client.post(f"{API}/ai/proposals/{uuid.uuid4()}/reject")
    assert resp.status_code == 404


def test_reject_existing_proposal(auth_client, db_session):
    # Find the user's workspace.
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    workspace_id = uuid.UUID(me["workspace"]["id"])
    user_id = uuid.UUID(me["user"]["id"])

    proposal = AiToolProposal(
        workspace_id=workspace_id,
        created_by=user_id,
        tool_name="create_task",
        tool_payload={"title": "Proposed task"},
        status="PENDING",
        risk_level="LOW",
    )
    db_session.add(proposal)
    db_session.commit()
    proposal_id = proposal.id

    # It appears as pending, then can be rejected.
    assert len(auth_client.get(f"{API}/ai/proposals").json()["data"]) == 1
    rejected = auth_client.post(f"{API}/ai/proposals/{proposal_id}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == "REJECTED"
    assert auth_client.get(f"{API}/ai/proposals").json()["data"] == []
