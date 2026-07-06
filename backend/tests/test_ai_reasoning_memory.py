"""Tests for reasoning_chat() memory integration (Task 11).

Covers:
(a) section_key acceptance (default / custom / omitted)
(b) spy: build() receives the custom section_key (uses runnable fake plans so
    build() is called on the happy path, after the early-exit check)
(c) "nama saya Joshua" -> Profile memory created synchronously
(d) with pre-seeded memory, the ANALYST-stage prompt contains the memory block
    exactly once; LATER-stage prompts (critic, synthesizer) contain zero
(e) extraction flush-failure (IntegrityError via broken _auto_save_or_suggest)
    doesn't break reasoning_chat
(f) direct guard: monkeypatch schedule_extraction to raise on the RUNNABLE/happy
    path -> reasoning_chat returns normally and run persisted; also covers the
    early-exit branch (no runnable agents)
"""

import uuid

import pytest

from app.core.principal import Principal
from app.domain.ai_memory import AiMemory
from app.services import memory_service
from app.services.ai_reasoning_service import reasoning_chat
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
    """Return a fake runnable ChatPlan that records prompts received."""

    class FakeResult:
        ok = True
        content = f"[{name}] grounded answer"
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
# (a) section_key acceptance
# ---------------------------------------------------------------------------


def test_reasoning_chat_accepts_default_section_key(auth_client, db_session):
    """reasoning_chat() accepts section_key='general' without error."""
    principal = _principal(auth_client)

    result = reasoning_chat(
        db_session,
        principal,
        message="Hello analyst",
        provider_ids=["ollama"],
        section_key="general",
    )
    assert result["session_id"] is not None


def test_reasoning_chat_accepts_custom_section_key(auth_client, db_session):
    """reasoning_chat() accepts a non-default section_key without error."""
    principal = _principal(auth_client)

    result = reasoning_chat(
        db_session,
        principal,
        message="Hello analyst",
        provider_ids=["ollama"],
        section_key="finance",
    )
    assert result["session_id"] is not None


def test_reasoning_chat_works_without_section_key(auth_client, db_session):
    """Omitting section_key uses the default 'general' and works without error."""
    principal = _principal(auth_client)

    result = reasoning_chat(
        db_session,
        principal,
        message="Hello analyst",
        provider_ids=["ollama"],
    )
    assert result["session_id"] is not None


# ---------------------------------------------------------------------------
# (b) section_key forwarding spy (requires runnable fake plans so build()
#     is reached after the early-exit check)
# ---------------------------------------------------------------------------


def test_reasoning_chat_forwards_section_key_to_build(auth_client, db_session, monkeypatch):
    """section_key is forwarded to memory_context_builder.build()."""
    principal = _principal(auth_client)

    received_keys: list[str | None] = []

    import app.services.ai_provider_router as _router
    import app.services.memory_context_builder as _mcb

    # Use fake runnable plans so the happy path (where build() is called) is exercised.
    monkeypatch.setattr(
        _router,
        "plan_chat",
        lambda db, principal, pid: _make_fake_plan(f"Agent-{pid}"),
    )

    original_build = _mcb.build

    def spy_build(db, principal, message, section_key=None):
        received_keys.append(section_key)
        return original_build(db, principal, message, section_key)

    monkeypatch.setattr(_mcb, "build", spy_build)

    reasoning_chat(
        db_session,
        principal,
        message="Test forwarding",
        provider_ids=["openai"],
        section_key="finance",
    )

    assert "finance" in received_keys, (
        f"Expected 'finance' to be forwarded to build(), got: {received_keys}"
    )


# ---------------------------------------------------------------------------
# (c) Rule-based extraction fires synchronously
# ---------------------------------------------------------------------------


def test_reasoning_chat_extracts_name_memory_synchronously(auth_client, db_session):
    """A message 'nama saya Joshua' creates a Profile memory via rule-based extraction.

    Even with no runnable provider (ollama not_configured), extraction still fires
    because the early-exit branch also calls schedule_extraction.
    """
    principal = _principal(auth_client)

    before = _memory_count(db_session, principal)

    result = reasoning_chat(
        db_session,
        principal,
        message="nama saya Joshua",
        provider_ids=["ollama"],
    )
    assert result["session_id"] is not None

    after = _memory_count(db_session, principal)
    assert after > before, "Expected at least one memory to be extracted after reasoning_chat"

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
# (d) Memory context injected into ANALYST prompt only — not later stages
# ---------------------------------------------------------------------------


def test_reasoning_chat_injects_memory_context_into_analyst_only(
    auth_client, db_session, monkeypatch
):
    """With a pre-seeded memory, the analyst-stage prompt contains the memory block
    exactly once. Critic and synthesizer prompts contain zero occurrences.

    The reasoning pipeline runs as: analyst -> (critic in deep) -> synthesizer.
    We use thinking_mode='deep' with 3 providers to hit all three stages.
    Memory prefix must appear in the analyst prompt only.
    """
    principal = _principal(auth_client)

    # Pre-seed a memory
    memory_service.upsert_memory(
        db_session,
        principal,
        category="Profile",
        title="User name",
        content="User's name is ReasoningTestUser.",
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

    result = reasoning_chat(
        db_session,
        principal,
        message="Do you know my name?",
        provider_ids=["openai", "anthropic", "gemini"],
        thinking_mode="deep",
    )
    assert result["session_id"] is not None
    assert captured_messages, "Expected plan.execute() to be called at least once"

    # Collect all user-role prompt strings across every execute() call.
    # In reasoning_chat, _call() wraps the prompt into [{"role": "user", "content": prompt}].
    all_user_prompts = [
        m["content"]
        for msgs in captured_messages
        for m in msgs
        if m.get("role") == "user"
    ]

    assert all_user_prompts, "Expected user prompts to be captured"

    # The analyst prompt is the first call — it should contain the memory block exactly once.
    # The analyst prompt contains ANALYST_PROMPT ("You are Analyst") from prompts.py.
    analyst_prompts = [p for p in all_user_prompts if "You are Analyst" in p]
    non_analyst_prompts = [p for p in all_user_prompts if "You are Analyst" not in p]

    assert analyst_prompts, "Expected at least one analyst-stage prompt to be captured"

    # Every analyst prompt must carry the memory prefix exactly once.
    for prompt in analyst_prompts:
        assert "ReasoningTestUser" in prompt, (
            f"Expected 'ReasoningTestUser' in analyst prompt, missing from: {prompt!r}"
        )
        assert prompt.count("[AI Memory") == 1, (
            f"Expected exactly one memory block in analyst prompt, got "
            f"{prompt.count('[AI Memory')}: {prompt!r}"
        )

    # Critic and synthesizer prompts must NOT contain the memory block.
    for prompt in non_analyst_prompts:
        assert "[AI Memory" not in prompt, (
            f"Memory block found in non-analyst (critic/synth) prompt: {prompt!r}"
        )


# ---------------------------------------------------------------------------
# (e) Extraction flush-failure does not break reasoning_chat
# ---------------------------------------------------------------------------


def test_reasoning_chat_completes_even_when_extraction_flush_fails(
    auth_client, db_session, monkeypatch
):
    """If db.flush() inside schedule_extraction fails, reasoning_chat() still returns normally.

    Uses the same flush-failure injection pattern as test_ai_debate_memory.py:
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
                content="User's name is ReasoningFlushFail.",
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

    result = reasoning_chat(
        db_session,
        principal,
        message="Hello analyst",
        provider_ids=["ollama"],
    )

    # reasoning_chat returned normally
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


# ---------------------------------------------------------------------------
# (f) schedule_extraction raising does not break reasoning_chat
# ---------------------------------------------------------------------------


def test_reasoning_chat_early_exit_guard_when_schedule_extraction_raises(
    auth_client, db_session, monkeypatch
):
    """Early-exit guard: if schedule_extraction raises when no agents are runnable,
    reasoning_chat() still returns normally.

    Uses unconfigured provider_ids (ollama, openai are not_configured) so the
    early-exit branch is reached.
    """
    principal = _principal(auth_client)

    import app.services.memory_extraction_service as _mes

    monkeypatch.setattr(
        _mes,
        "schedule_extraction",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("simulated extraction crash")),
    )

    result = reasoning_chat(
        db_session,
        principal,
        message="Hello analyst",
        provider_ids=["ollama", "openai"],
    )

    assert result is not None
    assert result.get("session_id") is not None
    assert result.get("responses") is not None


def test_reasoning_chat_happy_path_guard_when_schedule_extraction_raises(
    auth_client, db_session, monkeypatch
):
    """Happy-path guard: if schedule_extraction raises after a successful reasoning run,
    reasoning_chat() still returns normally AND the run/messages are persisted.

    This test exercises the try/except at the end of the happy path (after synthesis),
    distinct from the early-exit guard. Uses fake runnable agents so reasoning
    actually runs through analyst and synthesis phases.
    """
    principal = _principal(auth_client)

    import app.services.ai_provider_router as _router
    import app.services.memory_extraction_service as _mes

    monkeypatch.setattr(
        _router,
        "plan_chat",
        lambda db, principal, pid: _make_fake_plan(f"Agent-{pid}"),
    )

    monkeypatch.setattr(
        _mes,
        "schedule_extraction",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("simulated extraction crash")),
    )

    result = reasoning_chat(
        db_session,
        principal,
        message="Hello analyst",
        provider_ids=["openai"],
        thinking_mode="balance",
    )

    # reasoning_chat returned normally despite extraction raising
    assert result is not None
    assert result.get("session_id") is not None
    assert result.get("responses") is not None

    # The run row must have been persisted (committed before extraction attempt)
    from app.domain.ai import AiMultiAgentRun
    from sqlalchemy import select

    run_row = db_session.scalar(
        select(AiMultiAgentRun).where(
            AiMultiAgentRun.id == result["run"].id,
        )
    )
    assert run_row is not None, "Run was not persisted even though extraction failed"
    assert run_row.status in ("completed", "partial", "error"), (
        f"Expected run to have a terminal status, got: {run_row.status!r}"
    )
