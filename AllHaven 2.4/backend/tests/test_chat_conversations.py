"""Tests for ChatGPT-style conversations: groups, rename, move, delete, auto-title."""

from tests.conftest import API


def test_conversation_crud_groups_and_autotitle(auth_client):
    # New empty conversation -> "New Chat" (no messages yet).
    s = auth_client.post(f"{API}/ai/sessions", json={}).json()["data"]
    sid = s["id"]
    assert s["title"] in (None, "New Chat")
    assert s["group_id"] is None

    # Appears in the session list.
    listed = auth_client.get(f"{API}/ai/sessions").json()["data"]
    assert any(x["id"] == sid for x in listed)

    # First user message auto-titles the conversation (<= 40 chars).
    auth_client.post(
        f"{API}/ai/chat",
        json={"message": "Help me plan the AllHaven launch checklist for next week", "session_id": sid, "provider_id": "ollama"},
    )
    s2 = auth_client.get(f"{API}/ai/sessions/{sid}").json()["data"]
    assert s2["title"] and s2["title"] != "New Chat"
    assert len(s2["title"]) <= 41  # 40 + ellipsis

    # Messages persist and reload (user + assistant).
    msgs = auth_client.get(f"{API}/ai/sessions/{sid}/messages").json()["data"]
    assert any(m["role"] == "user" for m in msgs)
    assert any(m["role"] == "assistant" for m in msgs)

    # Create a group, move the conversation into it.
    g = auth_client.post(f"{API}/ai/groups", json={"name": "Launch"}).json()["data"]
    gid = g["id"]
    moved = auth_client.patch(f"{API}/ai/sessions/{sid}", json={"group_id": gid}).json()["data"]
    assert moved["group_id"] == gid

    # Rename the conversation.
    renamed = auth_client.patch(f"{API}/ai/sessions/{sid}", json={"title": "Launch plan"}).json()["data"]
    assert renamed["title"] == "Launch plan"

    # Remove from group (group_id=null), then delete the group (keeps the chat).
    out = auth_client.patch(f"{API}/ai/sessions/{sid}", json={"group_id": None}).json()["data"]
    assert out["group_id"] is None
    auth_client.delete(f"{API}/ai/groups/{gid}")
    assert all(x["id"] != gid for x in auth_client.get(f"{API}/ai/groups").json()["data"])

    # Delete the conversation -> gone from the list.
    auth_client.delete(f"{API}/ai/sessions/{sid}")
    assert all(x["id"] != sid for x in auth_client.get(f"{API}/ai/sessions").json()["data"])


def test_multi_agent_replies_persist_as_messages(auth_client):
    # Ollama is unconfigured here -> not_configured, but the reply is still
    # persisted as an assistant message so the thread reloads fully.
    run = auth_client.post(
        f"{API}/ai/chat/multi", json={"message": "halo", "provider_ids": ["ollama"]}
    ).json()["data"]
    sid = run["session_id"]
    msgs = auth_client.get(f"{API}/ai/sessions/{sid}/messages").json()["data"]
    assert sum(1 for m in msgs if m["role"] == "user") == 1
    assert sum(1 for m in msgs if m["role"] == "assistant") == 1
