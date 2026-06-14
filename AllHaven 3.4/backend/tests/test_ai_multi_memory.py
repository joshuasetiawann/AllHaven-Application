"""Tests for multi_chat() memory integration (Task 9).

Covers:
- multi_chat() accepts section_key without error
- Rule-based extraction fires synchronously: a name-triggering message creates a Profile memory
- When memories exist, system messages passed to providers contain the memory context block
- multi_chat() does not break when memory extraction fails (defensive try/except)
"""

import uuid

import pytest

from app.core.principal import Principal
from app.domain.ai_memory import AiMemory
from app.services import memory_service
from app.services.ai_multi_service import multi_chat
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


def test_multi_chat_accepts_section_key(auth_client, db_session):
    """multi_chat() accepts section_key without error (defaults to 'general')."""
    principal = _principal(auth_client)

    result = multi_chat(
        db_session,
        principal,
        message="Hello agents",
        provider_ids=["ollama"],
        section_key="general",
    )
    assert result["session_id"] is not None
    assert len(result["responses"]) == 1


def test_multi_chat_accepts_custom_section_key(auth_client, db_session):
    """multi_chat() accepts a custom section_key without error."""
    principal = _principal(auth_client)

    result = multi_chat(
        db_session,
        principal,
        message="Hello agents",
        provider_ids=["ollama"],
        section_key="finance",
    )
    assert result["session_id"] is not None


def test_multi_chat_works_without_section_key(auth_client, db_session):
    """Omitting section_key uses the default 'general' and works without error."""
    principal = _principal(auth_client)

    result = multi_chat(
        db_session,
        principal,
        message="Hello agents",
        provider_ids=["ollama"],
    )
    assert result["session_id"] is not None


# ---------------------------------------------------------------------------
# Rule-based memory extraction fires synchronously during multi_chat
# ---------------------------------------------------------------------------


def test_multi_chat_extracts_name_memory_synchronously(auth_client, db_session, monkeypatch):
    """A message 'nama saya Joshua' to multi_chat() creates a Profile memory.

    Because no real provider is configured (ollama not_configured), we get a
    not_configured response with no content — but rule-based extraction still
    fires on the user message and should produce a Profile memory.
    """
    principal = _principal(auth_client)

    before = _memory_count(db_session, principal)

    result = multi_chat(
        db_session,
        principal,
        message="nama saya Joshua",
        provider_ids=["ollama"],
    )
    # multi_chat returns normally
    assert result["session_id"] is not None

    after = _memory_count(db_session, principal)
    assert after > before, "Expected at least one memory to be extracted after multi_chat"

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
# Memory context injected into system messages
# ---------------------------------------------------------------------------


def test_multi_chat_injects_memory_context_into_system_messages(
    auth_client, db_session, monkeypatch
):
    """When memories exist, the system messages passed to provider plan.execute()
    contain the memory context block.

    We monkeypatch ai_provider_router.plan_chat to return a fake runnable plan
    whose execute() records the messages it received, so we can assert on the
    system message content without a real provider.
    """
    principal = _principal(auth_client)

    # Pre-seed a memory
    memory_service.upsert_memory(
        db_session,
        principal,
        category="Profile",
        title="User name",
        content="User's name is MultiTestUser.",
        source="test",
        sensitivity="LOW",
        confidence=0.95,
    )
    db_session.commit()

    captured_messages: list[list[dict]] = []

    # Build a fake ChatPlan that records messages and returns a "completed" result.
    from app.services.ai_provider_router import ChatPlan

    class FakeResult:
        ok = True
        content = "Hello from fake agent"
        error = None

    def _runner(messages, params=None):
        captured_messages.append(messages)
        return FakeResult()

    import app.services.ai_provider_router as _router

    monkeypatch.setattr(
        _router,
        "plan_chat",
        lambda db, principal, pid: ChatPlan(
            pid or "openai", "fake", False, True, True, "queued", "",
            _runner, supports_image=True, supports_tool_loop=False,
        ),
    )

    result = multi_chat(
        db_session,
        principal,
        message="Do you remember my name?",
        provider_ids=["openai"],
    )
    assert result["session_id"] is not None

    # Check that at least one captured message list has a system message with context
    assert captured_messages, "Expected plan.execute() to be called"
    system_messages = [
        m for msgs in captured_messages for m in msgs if m.get("role") == "system"
    ]
    assert system_messages, (
        "Expected a system message to be injected when memories exist"
    )
    combined = " ".join(m["content"] for m in system_messages)
    assert "MultiTestUser" in combined, (
        f"Expected 'MultiTestUser' in system messages, got: {combined!r}"
    )


def test_multi_chat_injects_memory_context_multi_agent(
    auth_client, db_session, monkeypatch
):
    """With multiple agents selected, each agent's system message gets the memory prefix."""
    principal = _principal(auth_client)

    # Pre-seed a memory
    memory_service.upsert_memory(
        db_session,
        principal,
        category="Profile",
        title="User name",
        content="User's name is TeamTestUser.",
        source="test",
        sensitivity="LOW",
        confidence=0.95,
    )
    db_session.commit()

    captured_messages: list[list[dict]] = []

    class FakeResult:
        ok = True
        content = "Hello from fake agent"
        error = None

    class FakePlan:
        runnable = True
        supports_image = True
        external = False
        provider_name = "fake"
        status = "completed"
        message = ""
        slot_role = ""

        def execute(self, messages, params=None):
            captured_messages.append(messages)
            return FakeResult()

    import app.services.ai_provider_router as _router

    monkeypatch.setattr(
        _router,
        "plan_chat",
        lambda db, principal, pid: FakePlan(),
    )

    result = multi_chat(
        db_session,
        principal,
        message="Who am I?",
        provider_ids=["openai", "anthropic"],
    )
    assert result["session_id"] is not None

    # Both agents should have system messages containing memory context
    assert len(captured_messages) == 2, f"Expected 2 agent calls, got {len(captured_messages)}"
    for msgs in captured_messages:
        sys_msgs = [m for m in msgs if m.get("role") == "system"]
        assert sys_msgs, "Each agent should receive a system message"
        assert any("TeamTestUser" in m["content"] for m in sys_msgs), (
            f"Memory context missing from agent system message: {sys_msgs}"
        )


# ---------------------------------------------------------------------------
# Build-placement invariant: build() only fires when an agent will run
# ---------------------------------------------------------------------------


def test_multi_chat_never_builds_memory_context_when_no_agent_runnable(
    auth_client, db_session, monkeypatch
):
    """build() must NOT be called when zero agents are runnable.

    build() has a mark_used side effect on every selected memory; firing it when
    no model will see the context would corrupt usage stats. multi_chat has no
    early RETURN (the run always completes with honest statuses), so this pins
    the gated build: context is built only when at least one agent is runnable.
    """
    principal = _principal(auth_client)

    import app.services.memory_context_builder as _mcb

    build_calls: list[tuple] = []

    def spy_build(db, principal, message, section_key=None):
        build_calls.append((message, section_key))
        return None

    monkeypatch.setattr(_mcb, "build", spy_build)

    # ollama/openai are not configured in tests -> zero runnable agents.
    result = multi_chat(
        db_session,
        principal,
        message="Hello agents",
        provider_ids=["ollama", "openai"],
    )

    assert result.get("session_id") is not None
    assert build_calls == [], (
        f"memory_context_builder.build() must not be called when no agent is "
        f"runnable, but it was called with: {build_calls}"
    )


# ---------------------------------------------------------------------------
# Extraction failure does not break multi_chat
# ---------------------------------------------------------------------------


def test_multi_chat_completes_even_when_extraction_flush_fails(
    auth_client, db_session, monkeypatch
):
    """If db.flush() inside schedule_extraction fails, multi_chat() still returns normally.

    Uses the same flush-failure injection pattern as test_ai_chat_memory.py:
    patch rule_based_extract to return a candidate, then patch _auto_save_or_suggest
    to db.add() an AiMemory with nullable=False columns set to None (IntegrityError).

    Assertions:
    (a) multi_chat() returns normally — no exception propagates.
    (b) the run and agent response rows are still accessible in the database.
    """
    principal = _principal(auth_client)

    from app.services import memory_extraction_service as _mes
    from app.services.memory_extraction_service import MemoryCandidate

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

    def _bad_save(db, principal, candidate, session_id):
        db.add(
            AiMemory(
                workspace_id=principal.workspace_id,
                title=None,    # nullable=False — triggers IntegrityError on flush
                content=None,  # nullable=False
            )
        )

    monkeypatch.setattr(_mes, "_auto_save_or_suggest", _bad_save)

    result = multi_chat(
        db_session,
        principal,
        message="Hello agents",
        provider_ids=["ollama"],
    )

    # (a) multi_chat returned normally
    assert result is not None
    assert result.get("session_id") is not None
    assert result.get("responses") is not None

    # (b) run row is accessible (was committed before extraction attempt)
    from app.domain.ai import AiMultiAgentRun
    from sqlalchemy import select

    run_row = db_session.scalar(
        select(AiMultiAgentRun).where(
            AiMultiAgentRun.id == result["run"].id,
        )
    )
    assert run_row is not None, "Run was not persisted even though extraction failed"
