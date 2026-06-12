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

    debate_chat(
        db_session,
        principal,
        message="Test forwarding",
        provider_ids=["openai", "anthropic"],
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
    # Opening prompts contain the phrase "one of" (from _opening_prompt); rebuttal prompts do not.
    opening_contents = []
    for msgs in captured_messages:
        for m in msgs:
            if m.get("role") == "user" and "one of" in m["content"]:
                opening_contents.append(m["content"])

    assert opening_contents, "Expected opening-round user messages to be passed to agents"

    # With rounds=1 and two providers there should be one opening prompt per agent.
    assert len(opening_contents) == 2, (
        f"Expected exactly 2 opening prompts (one per agent), got {len(opening_contents)}: {opening_contents!r}"
    )

    # EVERY opening prompt must carry the memory prefix — not just any one of them.
    for prompt in opening_contents:
        assert "DebateTestUser" in prompt, (
            f"Expected 'DebateTestUser' in ALL opening-round prompts, missing from: {prompt!r}"
        )
        assert prompt.count("[AI Memory") == 1, (
            f"Expected exactly one memory block in opening prompt, got {prompt.count('[AI Memory')}: {prompt!r}"
        )


# ---------------------------------------------------------------------------
# Memory prefix appears ONLY in opening round, never in rebuttal/synthesis
# ---------------------------------------------------------------------------


def test_debate_chat_memory_prefix_only_in_opening_round(
    auth_client, db_session, monkeypatch
):
    """Memory context is injected into opening-round prompts only.

    With rounds=2 and two agents: there are 2 opening prompts + 2 rebuttal prompts +
    1 synthesis prompt = 5 execute calls total. The memory block must appear exactly
    2 times (once per opening prompt) and zero times in rebuttal/synthesis prompts.
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
        rounds=2,
    )
    assert result["session_id"] is not None
    assert captured_messages, "Expected plan.execute() to be called at least once"

    # Collect ALL user-role prompt strings across every execute() call
    all_user_prompts = [
        m["content"]
        for msgs in captured_messages
        for m in msgs
        if m.get("role") == "user"
    ]

    assert all_user_prompts, "Expected user prompts to be captured"

    # Discriminate opening vs non-opening by the phrase used in _opening_prompt
    opening_prompts = [p for p in all_user_prompts if "one of" in p]
    non_opening_prompts = [p for p in all_user_prompts if "one of" not in p]

    # Exactly one [AI Memory block per opening prompt (2 agents)
    n_runnable = 2
    total_memory_occurrences = sum(p.count("[AI Memory") for p in all_user_prompts)
    assert total_memory_occurrences == n_runnable, (
        f"Expected memory block in exactly {n_runnable} prompts (opening only), "
        f"but total occurrences = {total_memory_occurrences}. "
        f"Opening prompts: {opening_prompts!r}, non-opening: {non_opening_prompts!r}"
    )

    # Rebuttal/synthesis prompts must have zero memory blocks
    for prompt in non_opening_prompts:
        assert "[AI Memory" not in prompt, (
            f"Memory block found in non-opening prompt: {prompt!r}"
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

    This is the early-exit path: unconfigured providers produce n_runnable == 0 which
    triggers the early-exit branch, confirming the try/except there handles it.
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


def test_debate_chat_happy_path_guard_when_schedule_extraction_raises(
    auth_client, db_session, monkeypatch
):
    """Happy-path guard: if schedule_extraction raises after a successful debate run,
    debate_chat() still returns normally AND the run/messages are persisted.

    This test exercises the try/except at the end of the happy path (after synthesis),
    distinct from the early-exit guard. Uses fake runnable agents so the debate
    actually runs through opening, rebuttal, and synthesis phases.
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

    result = debate_chat(
        db_session,
        principal,
        message="Hello agents",
        provider_ids=["openai", "anthropic"],
        rounds=1,
    )

    # debate_chat returned normally despite extraction raising
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
    assert run_row.status in ("completed", "partial"), (
        f"Expected run to be completed/partial, got: {run_row.status!r}"
    )
