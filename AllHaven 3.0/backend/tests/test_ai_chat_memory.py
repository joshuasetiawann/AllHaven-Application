"""Tests for ai_service.chat() memory integration (Task 8).

Covers:
- chat() accepts section_key without error
- Rule-based extraction fires synchronously after a chat turn containing a name
- Memory context is built and passed when memories exist
- Memory extraction never breaks the chat flow (errors swallowed)
"""

import uuid

import pytest

from app.core.principal import Principal
from app.domain.ai_memory import AiMemory
from app.services import ai_settings_service, memory_service
from app.services.ai_service import chat
from tests.conftest import API


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def _memory_count(db, principal) -> int:
    return (
        db.query(AiMemory)
        .filter(AiMemory.workspace_id == principal.workspace_id)
        .count()
    )


# ---------------------------------------------------------------------------
# section_key forwarding
# ---------------------------------------------------------------------------


def test_chat_accepts_section_key_via_http(auth_client):
    """The HTTP endpoint forwards section_key without error."""
    resp = auth_client.post(
        f"{API}/ai/chat",
        json={"message": "Hello there", "section_key": "finance"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["reply"]["role"] == "assistant"


def test_chat_accepts_section_key_general(auth_client):
    """Default section_key='general' works without error."""
    resp = auth_client.post(
        f"{API}/ai/chat",
        json={"message": "Hello there", "section_key": "general"},
    )
    assert resp.status_code == 200, resp.text


def test_chat_works_without_section_key(auth_client):
    """Omitting section_key uses the default and works without error."""
    resp = auth_client.post(
        f"{API}/ai/chat",
        json={"message": "Hello there"},
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Rule-based memory extraction fires synchronously during chat
# ---------------------------------------------------------------------------


def test_chat_extracts_name_memory_synchronously(auth_client, db_session):
    """A message with 'nama saya X' results in a Profile memory after chat()."""
    principal = _principal(auth_client)

    before = _memory_count(db_session, principal)

    result = chat(
        db_session,
        principal,
        message="nama saya Joshua",
    )
    # chat() should complete without error
    assert result["session_id"] is not None
    assert result["reply"].role == "assistant"

    after = _memory_count(db_session, principal)
    assert after > before, "Expected at least one memory to be extracted"

    memories = (
        db_session.query(AiMemory)
        .filter(AiMemory.workspace_id == principal.workspace_id)
        .all()
    )
    profile_memories = [m for m in memories if m.category == "Profile"]
    assert any("Joshua" in m.content for m in profile_memories), (
        f"Expected a Profile memory containing 'Joshua', got: {[m.content for m in profile_memories]}"
    )


def test_chat_extracts_english_name_memory(auth_client, db_session):
    """A message with 'my name is X' also triggers rule-based extraction."""
    principal = _principal(auth_client)

    result = chat(
        db_session,
        principal,
        message="My name is Alice.",
    )
    assert result["reply"].role == "assistant"

    memories = (
        db_session.query(AiMemory)
        .filter(
            AiMemory.workspace_id == principal.workspace_id,
            AiMemory.category == "Profile",
        )
        .all()
    )
    assert any("Alice" in m.content for m in memories)


# ---------------------------------------------------------------------------
# Memory extraction disabled → no memories written
# ---------------------------------------------------------------------------


def test_chat_extraction_skipped_when_auto_learning_disabled(auth_client, db_session):
    """When auto-learning is off, chat() still completes but writes no memories."""
    principal = _principal(auth_client)
    ai_settings_service.set_memory_settings(
        db_session, principal, {"auto_learning_enabled": False}
    )

    result = chat(
        db_session,
        principal,
        message="My name is Alice.",
    )
    assert result["reply"].role == "assistant"
    assert _memory_count(db_session, principal) == 0


# ---------------------------------------------------------------------------
# Memory context injection: existing memories are built into extra_context
# ---------------------------------------------------------------------------


def test_chat_builds_memory_context_from_existing_memories(
    auth_client, db_session, monkeypatch
):
    """If the user has existing Profile memories, memory_context_builder.build()
    returns a non-None block and it is passed to ai_orchestrator.run_with_tools."""
    principal = _principal(auth_client)

    # Pre-seed a memory
    memory_service.upsert_memory(
        db_session,
        principal,
        category="Profile",
        title="User name",
        content="User's name is TestUser.",
        source="test",
        sensitivity="LOW",
        confidence=0.95,
    )
    db_session.commit()

    captured = {}

    from app.services import ai_orchestrator as _orch

    original_run = _orch.run_with_tools

    def _capture_run(db, principal, *, message, session_id, provider_id=None, extra_context=None):
        captured["extra_context"] = extra_context
        return original_run(
            db, principal,
            message=message,
            session_id=session_id,
            provider_id=provider_id,
            extra_context=extra_context,
        )

    monkeypatch.setattr(_orch, "run_with_tools", _capture_run)

    chat(
        db_session,
        principal,
        message="Hello, do you remember my name?",
    )

    assert captured.get("extra_context") is not None, (
        "Expected extra_context to be passed to run_with_tools when memories exist"
    )
    assert "TestUser" in captured["extra_context"]


# ---------------------------------------------------------------------------
# Memory extraction never breaks chat flow
# ---------------------------------------------------------------------------


def test_chat_completes_even_when_extraction_flush_fails(auth_client, db_session, monkeypatch):
    """If the db.flush() inside schedule_extraction fails, chat() still returns normally.

    We force a real flush failure by:
    1. Patching rule_based_extract to return one valid MemoryCandidate.
    2. Patching _auto_save_or_suggest to db.add() an AiMemory with nullable=False
       columns set to None, so the subsequent db.flush() raises IntegrityError.

    This exercises the actual rollback-safety code path (db.rollback() inside
    schedule_extraction's except clause, and the outer try/except in ai_service.chat).

    Assertions:
    (a) chat() returns normally — no exception propagates to the caller.
    (b) the assistant ChatMessage was persisted in the database.
    """
    principal = _principal(auth_client)

    from app.services import memory_extraction_service as _mes
    from app.services.memory_extraction_service import MemoryCandidate

    # Patch rule_based_extract to return one valid candidate so _auto_save_or_suggest is called.
    def _one_candidate(text):
        return [
            MemoryCandidate(
                category="Profile",
                title="User name",
                content="User's name is TestFlushFail.",
                confidence=0.95,
                sensitivity="LOW",
                snippet="Hello there",
            )
        ]

    monkeypatch.setattr(_mes, "rule_based_extract", _one_candidate)

    # Patch _auto_save_or_suggest to add a broken AiMemory row (title=None violates NOT NULL),
    # guaranteeing the db.flush() at the end of schedule_extraction's try block raises IntegrityError.
    def _bad_save(db, principal, candidate, session_id):
        db.add(
            AiMemory(
                workspace_id=principal.workspace_id,
                title=None,   # nullable=False — triggers IntegrityError on flush
                content=None, # nullable=False
            )
        )

    monkeypatch.setattr(_mes, "_auto_save_or_suggest", _bad_save)

    result = chat(
        db_session,
        principal,
        message="Hello there",
    )

    # (a) chat() returned normally — no exception raised
    assert result is not None
    assert result.get("reply") is not None

    # (b) the assistant message was persisted
    from app.domain.ai import ChatMessage
    from sqlalchemy import select

    msg = db_session.scalar(
        select(ChatMessage).where(
            ChatMessage.session_id == result["session_id"],
            ChatMessage.role == "assistant",
        )
    )
    assert msg is not None, "Assistant message was not persisted when extraction flush failed"


# ---------------------------------------------------------------------------
# Failed orchestrator result must not feed content to the memory extractor
# ---------------------------------------------------------------------------


def test_failed_orchestrator_passes_empty_assistant_msg_to_extractor(
    auth_client, db_session, monkeypatch
):
    """When result["ok"] is False (provider unconfigured/blocked), extract_and_commit
    must receive assistant_msg='' so error-explainer text is not fed to the extractor.
    """
    principal = _principal(auth_client)

    captured = {}

    from app.services import memory_extraction_service as _mes

    original_extract = _mes.extract_and_commit

    def _spy(db, principal, *, user_msg, assistant_msg, session_id):
        captured["user_msg"] = user_msg
        captured["assistant_msg"] = assistant_msg
        # Still call through so the rest of the pipeline is not disrupted.
        return original_extract(
            db, principal,
            user_msg=user_msg,
            assistant_msg=assistant_msg,
            session_id=session_id,
        )

    monkeypatch.setattr(_mes, "extract_and_commit", _spy)

    test_message = "Hello, what is my name?"

    # Ollama is not configured in the test environment → result["ok"] is False.
    result = chat(
        db_session,
        principal,
        message=test_message,
        provider_id="ollama",
    )

    assert result["ai_configured"] is False, (
        "Expected ollama to be unconfigured in the test environment"
    )
    assert captured.get("user_msg") == test_message, (
        f"Expected user_msg='{test_message}', got: {captured.get('user_msg')!r}"
    )
    assert captured.get("assistant_msg") == "", (
        f"Expected assistant_msg='' for failed orchestrator, got: {captured.get('assistant_msg')!r}"
    )
