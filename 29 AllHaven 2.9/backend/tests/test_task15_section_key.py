"""Tests for Task 15: section_key field on multi/debate/reason endpoints.

Covers:
- MultiChatRequest, DebateChatRequest, ReasoningChatRequest each accept section_key
- section_key > 50 chars → 422 on all four chat endpoints (chat, multi, debate, reason)
- section_key is omitted → uses default "general" without error
- section_key is forwarded to the service (spy at service level)
"""

from __future__ import annotations

import uuid

import pytest

from app.core.principal import Principal
from tests.conftest import API


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


_LONG_SECTION_KEY = "x" * 51  # 51 chars > max_length=50


# ---------------------------------------------------------------------------
# /chat/multi — section_key
# ---------------------------------------------------------------------------


def test_multi_chat_accepts_section_key(auth_client):
    """multi endpoint accepts a valid section_key without error."""
    resp = auth_client.post(
        f"{API}/ai/chat/multi",
        json={
            "message": "Hello agents",
            "provider_ids": ["ollama"],
            "section_key": "finance",
        },
    )
    # 200 (even though ollama isn't configured — the endpoint processes it)
    assert resp.status_code == 200, resp.text


def test_multi_chat_accepts_no_section_key(auth_client):
    """multi endpoint works when section_key is omitted (uses default 'general')."""
    resp = auth_client.post(
        f"{API}/ai/chat/multi",
        json={"message": "Hello agents", "provider_ids": ["ollama"]},
    )
    assert resp.status_code == 200, resp.text


def test_multi_chat_rejects_long_section_key(auth_client):
    """section_key > 50 chars → 422 on /chat/multi."""
    resp = auth_client.post(
        f"{API}/ai/chat/multi",
        json={
            "message": "Hello",
            "provider_ids": ["ollama"],
            "section_key": _LONG_SECTION_KEY,
        },
    )
    assert resp.status_code == 422, resp.text


def test_multi_chat_forwards_section_key_to_service(auth_client, db_session, monkeypatch):
    """section_key value is forwarded to multi_chat() service."""
    principal = _principal(auth_client)

    captured = {}

    from app.services import ai_multi_service as _ms

    original = _ms.multi_chat

    def _spy(db, principal, *, message, provider_ids, session_id=None,
             images=None, thinking_mode="balance", section_key="general"):
        captured["section_key"] = section_key
        return original(
            db, principal,
            message=message,
            provider_ids=provider_ids,
            session_id=session_id,
            images=images,
            thinking_mode=thinking_mode,
            section_key=section_key,
        )

    monkeypatch.setattr(_ms, "multi_chat", _spy)

    auth_client.post(
        f"{API}/ai/chat/multi",
        json={
            "message": "Hello",
            "provider_ids": ["ollama"],
            "section_key": "notes",
        },
    )

    assert captured.get("section_key") == "notes", (
        f"Expected section_key='notes', got: {captured.get('section_key')!r}"
    )


# ---------------------------------------------------------------------------
# /chat/debate — section_key
# ---------------------------------------------------------------------------


def test_debate_chat_accepts_section_key(auth_client):
    """debate endpoint accepts a valid section_key without error."""
    resp = auth_client.post(
        f"{API}/ai/chat/debate",
        json={
            "message": "Debate this",
            "provider_ids": ["ollama"],
            "section_key": "tasks",
        },
    )
    assert resp.status_code == 200, resp.text


def test_debate_chat_accepts_no_section_key(auth_client):
    """debate endpoint works when section_key is omitted."""
    resp = auth_client.post(
        f"{API}/ai/chat/debate",
        json={"message": "Debate this", "provider_ids": ["ollama"]},
    )
    assert resp.status_code == 200, resp.text


def test_debate_chat_rejects_long_section_key(auth_client):
    """section_key > 50 chars → 422 on /chat/debate."""
    resp = auth_client.post(
        f"{API}/ai/chat/debate",
        json={
            "message": "Debate",
            "provider_ids": ["ollama"],
            "section_key": _LONG_SECTION_KEY,
        },
    )
    assert resp.status_code == 422, resp.text


def test_debate_chat_forwards_section_key_to_service(auth_client, db_session, monkeypatch):
    """section_key value is forwarded to debate_chat() service."""
    captured = {}

    from app.services import ai_debate_service as _ds

    original = _ds.debate_chat

    def _spy(db, principal, *, message, provider_ids, session_id=None,
             rounds=2, images=None, thinking_mode="balance", section_key="general"):
        captured["section_key"] = section_key
        return original(
            db, principal,
            message=message,
            provider_ids=provider_ids,
            session_id=session_id,
            rounds=rounds,
            images=images,
            thinking_mode=thinking_mode,
            section_key=section_key,
        )

    monkeypatch.setattr(_ds, "debate_chat", _spy)

    auth_client.post(
        f"{API}/ai/chat/debate",
        json={
            "message": "Debate",
            "provider_ids": ["ollama"],
            "section_key": "finance",
        },
    )

    assert captured.get("section_key") == "finance", (
        f"Expected section_key='finance', got: {captured.get('section_key')!r}"
    )


# ---------------------------------------------------------------------------
# /chat/reason — section_key
# ---------------------------------------------------------------------------


def test_reason_chat_accepts_section_key(auth_client):
    """reason endpoint accepts a valid section_key without error."""
    resp = auth_client.post(
        f"{API}/ai/chat/reason",
        json={
            "message": "Reason through this",
            "provider_ids": ["ollama"],
            "section_key": "calendar",
        },
    )
    assert resp.status_code == 200, resp.text


def test_reason_chat_accepts_no_section_key(auth_client):
    """reason endpoint works when section_key is omitted."""
    resp = auth_client.post(
        f"{API}/ai/chat/reason",
        json={"message": "Reason through this", "provider_ids": ["ollama"]},
    )
    assert resp.status_code == 200, resp.text


def test_reason_chat_rejects_long_section_key(auth_client):
    """section_key > 50 chars → 422 on /chat/reason."""
    resp = auth_client.post(
        f"{API}/ai/chat/reason",
        json={
            "message": "Reason",
            "provider_ids": ["ollama"],
            "section_key": _LONG_SECTION_KEY,
        },
    )
    assert resp.status_code == 422, resp.text


def test_reason_chat_forwards_section_key_to_service(auth_client, db_session, monkeypatch):
    """section_key value is forwarded to reasoning_chat() service."""
    captured = {}

    from app.services import ai_reasoning_service as _rs

    original = _rs.reasoning_chat

    def _spy(db, principal, *, message, provider_ids, session_id=None,
             thinking_mode="balance", images=None, section_key="general"):
        captured["section_key"] = section_key
        return original(
            db, principal,
            message=message,
            provider_ids=provider_ids,
            session_id=session_id,
            thinking_mode=thinking_mode,
            images=images,
            section_key=section_key,
        )

    monkeypatch.setattr(_rs, "reasoning_chat", _spy)

    auth_client.post(
        f"{API}/ai/chat/reason",
        json={
            "message": "Reason",
            "provider_ids": ["ollama"],
            "section_key": "projects",
        },
    )

    assert captured.get("section_key") == "projects", (
        f"Expected section_key='projects', got: {captured.get('section_key')!r}"
    )


# ---------------------------------------------------------------------------
# /chat — section_key validation (existing endpoint, Task 8 already wired)
# ---------------------------------------------------------------------------


def test_chat_rejects_long_section_key(auth_client):
    """section_key > 50 chars → 422 on /chat (all four endpoints reject it)."""
    resp = auth_client.post(
        f"{API}/ai/chat",
        json={"message": "Hello", "section_key": _LONG_SECTION_KEY},
    )
    assert resp.status_code == 422, resp.text
