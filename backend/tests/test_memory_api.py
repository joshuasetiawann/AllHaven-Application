"""Tests for the AI Memory REST API (Task 14).

Covers:
- list (empty, seeded, category filter)
- create (valid, invalid category → 422, blank title → 422)
- search (match, no-match, missing q → 422)
- update (title, content, category)
- delete
- enable / disable toggle
- suggestions list / approve / reject (seeded via memory_service.create_suggestion)
- approve creates/updates a memory (MemoryOut returned)
- settings GET defaults + PUT roundtrip + unknown keys ignored
- clear (returns count, memories gone afterwards)
- workspace isolation (second user cannot see/modify first user's memories)
- sync/supabase returns graceful 'not available' response before Task 16 is present
"""

from __future__ import annotations

import uuid

import pytest

from app.core.principal import Principal
from app.services import memory_service
from tests.conftest import API

MEMORY_PREFIX = f"{API}/ai/memory"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def _register_second(client):
    """Register a second user and return an independent authenticated client."""
    resp = client.post(
        f"{API}/auth/register",
        json={
            "email": "second@example.com",
            "password": "password123",
            "full_name": "Second User",
        },
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    from fastapi.testclient import TestClient
    from app.main import app
    other = TestClient(app)
    other.headers.update({"Authorization": f"Bearer {token}"})
    return other


# ---------------------------------------------------------------------------
# List memories
# ---------------------------------------------------------------------------


def test_list_memories_empty(auth_client):
    resp = auth_client.get(MEMORY_PREFIX)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == []


def test_list_memories_seeded(auth_client, db_session):
    principal = _principal(auth_client)
    memory_service.create_memory(
        db_session, principal,
        category="Profile", title="User name", content="User's name is Alice.",
        source="manual", sensitivity="LOW",
    )
    db_session.commit()

    resp = auth_client.get(MEMORY_PREFIX)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "User name"
    assert data[0]["category"] == "Profile"


def test_list_memories_category_filter(auth_client, db_session):
    principal = _principal(auth_client)
    memory_service.create_memory(
        db_session, principal,
        category="Profile", title="User name", content="Alice",
        source="manual", sensitivity="LOW",
    )
    memory_service.create_memory(
        db_session, principal,
        category="Technical", title="Preferred language", content="Python",
        source="manual", sensitivity="LOW",
    )
    db_session.commit()

    resp = auth_client.get(MEMORY_PREFIX, params={"category": "Profile"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["category"] == "Profile"

    resp2 = auth_client.get(MEMORY_PREFIX, params={"category": "Technical"})
    assert len(resp2.json()["data"]) == 1
    assert resp2.json()["data"][0]["category"] == "Technical"


# ---------------------------------------------------------------------------
# Create memory
# ---------------------------------------------------------------------------


def test_create_memory_valid(auth_client):
    resp = auth_client.post(
        MEMORY_PREFIX,
        json={"category": "Goals", "title": "Ship v1", "content": "Ship v1 by end of quarter."},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["title"] == "Ship v1"
    assert data["category"] == "Goals"
    assert data["source"] == "manual"
    assert data["enabled"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_memory_invalid_category(auth_client):
    resp = auth_client.post(
        MEMORY_PREFIX,
        json={"category": "InvalidCategory", "title": "T", "content": "C"},
    )
    assert resp.status_code == 422, resp.text


def test_create_memory_blank_title(auth_client):
    resp = auth_client.post(
        MEMORY_PREFIX,
        json={"category": "Profile", "title": "", "content": "Some content"},
    )
    assert resp.status_code == 422, resp.text


def test_create_memory_blank_content(auth_client):
    resp = auth_client.post(
        MEMORY_PREFIX,
        json={"category": "Profile", "title": "Title", "content": ""},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Search memories
# ---------------------------------------------------------------------------


def test_search_memories_match(auth_client, db_session):
    principal = _principal(auth_client)
    memory_service.create_memory(
        db_session, principal,
        category="Profile", title="User name", content="User's name is SearchableName.",
        source="manual", sensitivity="LOW",
    )
    db_session.commit()

    resp = auth_client.get(f"{MEMORY_PREFIX}/search", params={"q": "SearchableName"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data) >= 1
    assert any("SearchableName" in m["content"] for m in data)


def test_search_memories_no_match(auth_client):
    resp = auth_client.get(f"{MEMORY_PREFIX}/search", params={"q": "xyzzy_no_match_ever"})
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_search_memories_missing_q(auth_client):
    resp = auth_client.get(f"{MEMORY_PREFIX}/search")
    assert resp.status_code == 422, resp.text


def test_search_memories_empty_q(auth_client):
    # Empty string is also < min_length=1 → 422
    resp = auth_client.get(f"{MEMORY_PREFIX}/search", params={"q": ""})
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Update memory
# ---------------------------------------------------------------------------


def test_update_memory(auth_client):
    create = auth_client.post(
        MEMORY_PREFIX,
        json={"category": "Profile", "title": "Old title", "content": "Old content"},
    )
    memory_id = create.json()["data"]["id"]

    resp = auth_client.patch(
        f"{MEMORY_PREFIX}/{memory_id}",
        json={"title": "New title", "content": "New content", "category": "Goals"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["title"] == "New title"
    assert data["content"] == "New content"
    assert data["category"] == "Goals"


def test_update_memory_partial(auth_client):
    create = auth_client.post(
        MEMORY_PREFIX,
        json={"category": "Profile", "title": "My title", "content": "My content"},
    )
    memory_id = create.json()["data"]["id"]

    # Only update title
    resp = auth_client.patch(
        f"{MEMORY_PREFIX}/{memory_id}",
        json={"title": "Updated title only"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["title"] == "Updated title only"
    assert data["content"] == "My content"  # unchanged


def test_update_memory_not_found(auth_client):
    fake_id = str(uuid.uuid4())
    resp = auth_client.patch(
        f"{MEMORY_PREFIX}/{fake_id}",
        json={"title": "Whatever"},
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Delete memory
# ---------------------------------------------------------------------------


def test_delete_memory(auth_client):
    create = auth_client.post(
        MEMORY_PREFIX,
        json={"category": "Profile", "title": "To delete", "content": "Will be deleted"},
    )
    memory_id = create.json()["data"]["id"]

    delete_resp = auth_client.delete(f"{MEMORY_PREFIX}/{memory_id}")
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_resp.json()["data"]["id"] == memory_id

    # Should be gone from list
    list_resp = auth_client.get(MEMORY_PREFIX)
    ids = [m["id"] for m in list_resp.json()["data"]]
    assert memory_id not in ids


def test_delete_memory_not_found(auth_client):
    fake_id = str(uuid.uuid4())
    resp = auth_client.delete(f"{MEMORY_PREFIX}/{fake_id}")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Enable / disable toggle
# ---------------------------------------------------------------------------


def test_enable_disable_toggle(auth_client):
    create = auth_client.post(
        MEMORY_PREFIX,
        json={"category": "Profile", "title": "Toggle me", "content": "Some content"},
    )
    memory_id = create.json()["data"]["id"]
    assert create.json()["data"]["enabled"] is True

    # Disable
    resp = auth_client.post(f"{MEMORY_PREFIX}/{memory_id}/disable")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["enabled"] is False

    # Enable again
    resp2 = auth_client.post(f"{MEMORY_PREFIX}/{memory_id}/enable")
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["data"]["enabled"] is True


# ---------------------------------------------------------------------------
# Suggestions: list / approve / reject
# ---------------------------------------------------------------------------


def test_list_suggestions_empty(auth_client):
    resp = auth_client.get(f"{MEMORY_PREFIX}/suggestions")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == []


def test_list_suggestions_seeded(auth_client, db_session):
    principal = _principal(auth_client)
    memory_service.create_suggestion(
        db_session, principal,
        category="Profile",
        title="Extracted name",
        content="User's name is Bob.",
        source_session_id=None,
        source_snippet="my name is Bob",
        confidence=0.9,
        sensitivity="LOW",
    )
    db_session.commit()

    resp = auth_client.get(f"{MEMORY_PREFIX}/suggestions")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "Extracted name"
    assert data[0]["status"] == "pending"


def test_approve_suggestion_creates_memory(auth_client, db_session):
    principal = _principal(auth_client)
    suggestion = memory_service.create_suggestion(
        db_session, principal,
        category="Profile",
        title="Approved name",
        content="User's name is Charlie.",
        source_session_id=None,
        source_snippet="name is Charlie",
        confidence=0.85,
        sensitivity="LOW",
    )
    db_session.commit()

    resp = auth_client.post(f"{MEMORY_PREFIX}/suggestions/{suggestion.id}/approve")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # Returns MemoryOut
    assert data["title"] == "Approved name"
    assert data["content"] == "User's name is Charlie."
    assert "id" in data
    assert "created_at" in data

    # Memory should appear in list
    list_resp = auth_client.get(MEMORY_PREFIX)
    titles = [m["title"] for m in list_resp.json()["data"]]
    assert "Approved name" in titles


def test_reject_suggestion(auth_client, db_session):
    principal = _principal(auth_client)
    suggestion = memory_service.create_suggestion(
        db_session, principal,
        category="Preferences",
        title="Rejected pref",
        content="User prefers dark mode.",
        source_session_id=None,
        source_snippet="I prefer dark mode",
        confidence=0.7,
        sensitivity="LOW",
    )
    db_session.commit()

    resp = auth_client.post(f"{MEMORY_PREFIX}/suggestions/{suggestion.id}/reject")
    assert resp.status_code == 200, resp.text
    assert str(suggestion.id) == resp.json()["data"]["id"]

    # Suggestion no longer in pending list
    list_resp = auth_client.get(f"{MEMORY_PREFIX}/suggestions")
    ids = [s["id"] for s in list_resp.json()["data"]]
    assert str(suggestion.id) not in ids


def test_approve_suggestion_not_found(auth_client):
    fake_id = str(uuid.uuid4())
    resp = auth_client.post(f"{MEMORY_PREFIX}/suggestions/{fake_id}/approve")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Settings: GET defaults + PUT roundtrip + unknown keys ignored
# ---------------------------------------------------------------------------


def test_settings_get_defaults(auth_client):
    resp = auth_client.get(f"{MEMORY_PREFIX}/settings")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["auto_learning_enabled"] is True
    assert data["require_approval_sensitive"] is True


def test_settings_put_roundtrip(auth_client):
    resp = auth_client.put(
        f"{MEMORY_PREFIX}/settings",
        json={"auto_learning_enabled": False, "require_approval_sensitive": False},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["auto_learning_enabled"] is False
    assert data["require_approval_sensitive"] is False

    # Verify GET reflects the change
    get_resp = auth_client.get(f"{MEMORY_PREFIX}/settings")
    assert get_resp.json()["data"]["auto_learning_enabled"] is False


def test_settings_put_ignores_unknown_keys(auth_client):
    """Unknown keys in MemorySettingsUpdate are ignored (Pydantic strips extras)."""
    # Send a known key alongside a completely unknown key.
    resp = auth_client.put(
        f"{MEMORY_PREFIX}/settings",
        json={"auto_learning_enabled": True, "hack_key": True},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["auto_learning_enabled"] is True
    # The unknown key must NOT appear in the response.
    assert "hack_key" not in data

    # A follow-up GET must also not carry the unknown key.
    get_resp = auth_client.get(f"{MEMORY_PREFIX}/settings")
    assert get_resp.status_code == 200
    assert "hack_key" not in get_resp.json()["data"]


# ---------------------------------------------------------------------------
# Clear all memories
# ---------------------------------------------------------------------------


def test_clear_all_memories(auth_client):
    # Create two memories
    for i in range(2):
        auth_client.post(
            MEMORY_PREFIX,
            json={"category": "Profile", "title": f"Memory {i}", "content": f"Content {i}"},
        )

    list_resp = auth_client.get(MEMORY_PREFIX)
    assert len(list_resp.json()["data"]) == 2

    clear_resp = auth_client.post(f"{MEMORY_PREFIX}/clear")
    assert clear_resp.status_code == 200, clear_resp.text
    assert clear_resp.json()["data"]["deleted"] == 2

    # All gone
    list_after = auth_client.get(MEMORY_PREFIX)
    assert list_after.json()["data"] == []


def test_clear_all_memories_empty(auth_client):
    resp = auth_client.post(f"{MEMORY_PREFIX}/clear")
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] == 0


def test_clear_removes_non_active_status_memories(auth_client, db_session):
    """POST /clear must delete memories regardless of status (not just 'active')."""
    principal = _principal(auth_client)

    # Create one memory via the API (status='active').
    auth_client.post(
        MEMORY_PREFIX,
        json={"category": "Profile", "title": "Active Mem", "content": "Active"},
    )

    # Seed a 'stale' memory directly via the ORM, bypassing the API.
    stale_mem = memory_service.create_memory(
        db_session,
        principal,
        category="Profile",
        title="Stale Mem",
        content="Should be cleared",
        source="manual",
    )
    stale_mem.status = "stale"
    db_session.commit()

    # /clear should wipe both memories.
    clear_resp = auth_client.post(f"{MEMORY_PREFIX}/clear")
    assert clear_resp.status_code == 200, clear_resp.text
    assert clear_resp.json()["data"]["deleted"] == 2

    # Nothing left — even list with no status filter shows empty.
    list_resp = auth_client.get(MEMORY_PREFIX)
    assert list_resp.json()["data"] == []


# ---------------------------------------------------------------------------
# Workspace isolation
# ---------------------------------------------------------------------------


def test_workspace_isolation_list(auth_client, client):
    """Second user cannot see first user's memories."""
    auth_client.post(
        MEMORY_PREFIX,
        json={"category": "Profile", "title": "User A memory", "content": "A private memory"},
    )

    other = _register_second(client)
    other_resp = other.get(MEMORY_PREFIX)
    assert other_resp.status_code == 200
    data = other_resp.json()["data"]
    titles = [m["title"] for m in data]
    assert "User A memory" not in titles


def test_workspace_isolation_update(auth_client, client, db_session):
    """Second user cannot update first user's memory."""
    create = auth_client.post(
        MEMORY_PREFIX,
        json={"category": "Profile", "title": "Protected", "content": "Secret"},
    )
    memory_id = create.json()["data"]["id"]

    other = _register_second(client)
    resp = other.patch(
        f"{MEMORY_PREFIX}/{memory_id}",
        json={"title": "Hijacked"},
    )
    assert resp.status_code == 404, resp.text


def test_workspace_isolation_delete(auth_client, client):
    """Second user cannot delete first user's memory."""
    create = auth_client.post(
        MEMORY_PREFIX,
        json={"category": "Profile", "title": "Protected delete", "content": "Cannot delete"},
    )
    memory_id = create.json()["data"]["id"]

    other = _register_second(client)
    resp = other.delete(f"{MEMORY_PREFIX}/{memory_id}")
    assert resp.status_code == 404, resp.text


def test_workspace_isolation_suggestions(auth_client, client, db_session):
    """Second user cannot approve first user's suggestion."""
    principal = _principal(auth_client)
    suggestion = memory_service.create_suggestion(
        db_session, principal,
        category="Profile",
        title="Private suggestion",
        content="Cannot approve this.",
        source_session_id=None,
        source_snippet="private snippet",
        confidence=0.8,
        sensitivity="LOW",
    )
    db_session.commit()

    other = _register_second(client)
    resp = other.post(f"{MEMORY_PREFIX}/suggestions/{suggestion.id}/approve")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Supabase sync — graceful 'not available' before Task 16
# ---------------------------------------------------------------------------


def test_sync_supabase_returns_graceful_response(auth_client):
    """The sync endpoint returns a 200 with status='not_available' when
    supabase_sync_service has not been implemented yet (Task 16 pending).

    If supabase_sync_service IS present and not configured (returns
    status='not_configured'), that is also acceptable — the endpoint must
    never return a 500 or raise an ImportError to the client.
    """
    resp = auth_client.post(f"{MEMORY_PREFIX}/sync/supabase")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] in ("not_available", "not_configured", "syncing"), (
        f"Unexpected status: {data['status']!r}"
    )
