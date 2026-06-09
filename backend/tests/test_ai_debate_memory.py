"""Tests for debate_chat() memory integration (Task 10).

Covers:
- debate_chat() accepts section_key (default / custom / omitted)
- section_key is actually forwarded to memory_context_builder.build()
- Rule-based extraction fires synchronously: a name-triggering message creates a Profile memory
- When memories exist, the opening-round prompts passed to providers contain the memory content
- debate_chat() does not break when memory extraction flush fails (defensive try/except)
- debate_chat() does not break when schedule_extraction itself raises (service-level guard)
"""

import uuid

import pytest

from app.core.principal import Principal
from app.domain.ai_memory import AiMemory
from app.services import memory_service
from app.services.ai_debate_service import debate_chat
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


def _memory_count(db, principal) -> int:
    return (
        db.query(AiMemory)
        .filter(AiMemory.workspace_id == principal.workspace_id)
        .count()
    )


def _make_fake_plan(name: str, captured: list | None = None):
    """Return a fake runnable ChatPlan that records received messages."""
    from app.services.ai_providers.base import ChatResult

    class FakeResult:
        ok = True
        content = f"[{name}] answer"
        error = None

    class FakePlan:
        runnable = True
        supports_image = True
        external = False
        provider_name = name
        status = "completed"
        message = ""
        slot_role = ""

        def execute(self, messages, params=None):
            if captured is not None:
                captured.append(messages)
            return FakeResult()

    return FakePlan()


# ---------------------------------------------------------------------------
# section_key acceptance
# ---------------------------------------------------------------------------


def test_debate_chat_accepts_default_section_key(auth_client, db_session):
    """debate_chat() accepts section_key='general' without error."""
    principal = _principal(auth_client)

    result = debate_chat(
        db_session,
        principal,
        message="Hello agents",
        provider_ids=["ollama", "openai"],
        section_key="general",
    )
    assert result["session_id"] is not None


def test_debate_chat_accepts_custom_section_key(auth_client, db_session):
    """debate_chat() accepts a non-default section_key without error."""
    principal = _principal(auth_client)

    result = debate_chat(
        db_session,
        principal,
        message="Hello agents",
        provider_ids=["ollama", "openai"],
        section_key="finance",
    )
    assert result["session_id"] is not None


def test_debate_chat_works_without_section_key(auth_client, db_session):
    """Omitting section_key uses the default 'general' and works without error."""
    principal = _principal(auth_client)

    result = debate_chat(
        db_session,
        principal,
        message="Hello agents",
        provider_ids=["ollama", "openai"],
    )
    assert result["session_id"] is not None


# ---------------------------------------------------------------------------
# section_key forwarding verification
# ---------------------------------------------------------------------------


def test_debate_chat_forwards_section_key_to_build(auth_client, db_session, monkeypatch):
    """section_key is forwarded to memory_context_builder.build()."""
    principal = _principal(auth_client)

    received_keys: list[str | None] = []

    import app.services.memory_context_builder as _mcb

    original_build = _mcb.build

    def spy_build(db, principal, message, section_key=None):
        received_keys.append(section_key)
        return original_build(db, principal, message, section_key)

    monkeypatch.setattr(_mcb, "build", spy_build)

    debate_chat(
        db_session,
        principal,
        message="Test forwarding",
        provider_ids=["ollama", "openai"],
        section_key="finance",
    )

    assert "finance" in received_keys, (
        f"Expected 'finance' to be forwarded to build(), got: {received_keys}"
    )


# ---------------------------------------------------------------------------
# Rule-based memory extraction fires synchronously during debate_chat
# ---------------------------------------------------------------------------


def test_debate_chat_extracts_name_memory_synchronously(auth_client, db_session):
    """A message 'nama saya Joshua' creates a Profile memory via rule-based extraction.

    Even though no provider is configured (ollama not_configured), extraction fires
    on the user message.
    """
    principal = _principal(auth_client)

    before = _memory_count(db_session, principal)

    result = debate_chat(
        db_session,
        principal,
        message="nama saya Joshua",
        provider_ids=["ollama", "openai"],
    )
    assert result["session_id"] is not None

    after = _memory_count(db_session, principal)
    assert after > before, "Expected at least one memory to be extracted after debate_chat"

    memories = (
        db_session.query(AiMemory)
        .filter(AiMemory.workspace_id == principal.workspace_id)
        .all()
    )
    profile_memories = [m for m in memories if m.category == "Profile"]
    assert any("Joshua" in m.content for m in profile_memories), (
        f"Expected a Profile memory containing 'Joshua', got: {[m.content for m in profile_memories]}"
    )


# ---------------------------------------------------------------------------
# Memory context injected into opening-round prompts
# ---------------------------------------------------------------------------


def test_debate_chat_injects_memory_context_into_opening_round(
    auth_client, db_session, monkeypatch
):
    """When memories exist, the opening-round prompt content passed to providers
    contains the memory context block.

    We monkeypatch ai_provider_router.plan_chat to return a fake plan that records
    all messages it receives so we can inspect opening-round prompts.
    """
    principal = _principal(auth_client)

    # Pre-seed a memory
    memory_service.upsert_memory(
        db_session,
        principal,
        category="Profile",
        title="User name",
        content="User's name is DebateTestUser.",
        source="test",
        sensitivity="LOW",
        confidence=0.95,
    )
    db_session.commit()

    captured_messages: list[list[dict]] = []

    import app.services.ai_provider_router as _router

    monkeypatch.setattr(
        _router,
        "plan_chat",
        lambda db, principal, pid: _make_fake_plan(f"Agent-{pid}", captured_messages),
    )

    result = debate_chat(
        db_session,
        principal,
        message="Do you know my name?",
        provider_ids=["openai", "anthropic"],
        rounds=1,
    )
    assert result["session_id"] is not None

    assert captured_messages, "Expected plan.execute() to be called at least once"

    # Inspect opening-round calls: the user message content should contain the memory prefix.
    # In debate_chat, _run_round sends [{"role": "user", "content": prompt, "images": [...]}]
    opening_contents = []
    for msgs in captured_messages:
        for m in msgs:
            if m.get("role") == "user":
                opening_contents.append(m["content"])

    assert opening_contents, "Expected user messages to be passed to agents"
    assert any("DebateTestUser" in c for c in opening_contents), (
        f"Expected 'DebateTestUser' in opening-round prompts, got: {opening_contents!r}"
    )


# ---------------------------------------------------------------------------
# Extraction failure does not break debate_chat
# ---------------------------------------------------------------------------


def test_debate_chat_completes_even_when_extraction_flush_fails(
    auth_client, db_session, monkeypatch
):
    """If db.flush() inside schedule_extraction fails, debate_chat() still returns normally.

    Uses the same flush-failure injection pattern as test_ai_multi_memory.py:
    patch rule_based_extract to return a candidate, then patch _auto_save_or_suggest
    to db.add() an AiMemory with nullable=False columns set to None (IntegrityError).
    """
    principal = _principal(auth_client)

    from app.services import memory_extraction_service as _mes
    from app.services.memory_extraction_service import MemoryCandidate

    def _one_candidate(text):
        return [
            MemoryCandidate(
                category="Profile",
                title="User name",
                content="User's name is DebateFlushFail.",
                confidence=0.95,
                sensitivity="LOW",
                snippet="Hello there",
            )
        ]

    monkeypatch.setattr(_mes, "rule_based_extract", _one_candidate)

    def _bad_save(db, principal, candidate, session_id):
        db.add(
            AiMemory(
                workspace_id=principal.workspace_id,
                title=None,    # nullable=False — triggers IntegrityError on flush
                content=None,  # nullable=False
            )
        )

    monkeypatch.setattr(_mes, "_auto_save_or_suggest", _bad_save)

    result = debate_chat(
        db_session,
        principal,
        message="Hello agents",
        provider_ids=["ollama", "openai"],
    )

    # debate_chat returned normally
    assert result is not None
    assert result.get("session_id") is not None
    assert result.get("responses") is not None

    # run row is accessible (was committed before extraction attempt)
    from app.domain.ai import AiMultiAgentRun
    from sqlalchemy import select

    run_row = db_session.scalar(
        select(AiMultiAgentRun).where(
            AiMultiAgentRun.id == result["run"].id,
        )
    )
    assert run_row is not None, "Run was not persisted even though extraction failed"


def test_debate_chat_completes_even_when_schedule_extraction_raises(
    auth_client, db_session, monkeypatch
):
    """If schedule_extraction itself raises, debate_chat() still returns normally.

    This is the service-level guard test: monkeypatches the service function directly
    to raise, confirming the try/except in debate_chat handles it.
    """
    principal = _principal(auth_client)

    import app.services.memory_extraction_service as _mes

    monkeypatch.setattr(
        _mes,
        "schedule_extraction",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("simulated extraction crash")),
    )

    result = debate_chat(
        db_session,
        principal,
        message="Hello agents",
        provider_ids=["ollama", "openai"],
    )

    assert result is not None
    assert result.get("session_id") is not None
    assert result.get("responses") is not None
