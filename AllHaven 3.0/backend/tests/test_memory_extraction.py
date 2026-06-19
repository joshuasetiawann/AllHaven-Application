"""Tests for memory_extraction_service: secret-safety, rule-based extraction,
auto-save vs suggest routing, and the never-raise guarantee of schedule_extraction.

Service layer runs against the real test DB (no mocks); only the LLM provider
plan is stubbed where needed.
"""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.principal import Principal
from app.domain.ai_memory import AiMemory, AiMemorySuggestion
from app.services import ai_settings_service
from app.services.memory_extraction_service import (
    MemoryCandidate,
    _auto_save_or_suggest,
    _contains_secret,
    _llm_extract_candidates,
    rule_based_extract,
    schedule_extraction,
)
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


def _suggestion_count(db, principal) -> int:
    return (
        db.query(AiMemorySuggestion)
        .filter(AiMemorySuggestion.workspace_id == principal.workspace_id)
        .count()
    )


# --- secret detection blocks extraction entirely -------------------------------


@pytest.mark.parametrize(
    "secret",
    [
        "sk-abc123DEF456ghi789",                                # OpenAI-style key
        "ghp_abcdefgh12345678",                                 # vendor-prefixed token
        "xoxb-is-not-this-one ghp_zzzzzzzzzz",                  # GitHub PAT prefix
        "AKIAIOSFODNN7EXAMPLE",                                 # AWS access key id
        "Bearer abcDEF123.456-xyz_789",                         # bearer token
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIx",    # JWT
        "a" * 45,                                               # long opaque token
        "password=hunter2plus",                                 # key=value password
        "api_key: zzz-top-secret",                              # key: value api key
    ],
)
def test_rule_based_extract_skips_message_containing_secret(secret):
    text = f"My name is Alice. By the way here is something: {secret}"
    assert _contains_secret(text) is True
    assert rule_based_extract(text) == []


def test_plain_message_is_not_flagged_as_secret():
    assert _contains_secret("My name is Alice.") is False


# --- rule-based extraction (Indonesian + English) -------------------------------


def test_extracts_indonesian_name():
    candidates = rule_based_extract("Nama saya Budi.")
    assert len(candidates) == 1
    c = candidates[0]
    assert c.category == "Profile"
    assert c.title == "User name"
    assert "Budi" in c.content
    assert c.sensitivity == "LOW"
    assert c.confidence >= 0.9


def test_extracts_english_name():
    candidates = rule_based_extract("My name is Alice.")
    assert len(candidates) == 1
    c = candidates[0]
    assert c.category == "Profile"
    assert c.title == "User name"
    assert "Alice" in c.content


def test_dedups_by_category_and_title_within_one_message():
    # Both the Indonesian and the English name rules match; only the first
    # (Profile:User name) candidate is kept.
    candidates = rule_based_extract("Nama saya Budi. My name is Alice.")
    keys = [f"{c.category}:{c.title}" for c in candidates]
    assert keys.count("Profile:User name") == 1
    assert len(candidates) == 1
    assert "Budi" in candidates[0].content  # first matching rule wins


def test_skips_values_shorter_than_two_chars():
    # "A " matches the regex group but strips down to a single character.
    assert rule_based_extract("My name is A .") == []


def test_extracts_direct_style_and_ai_needs():
    candidates = rule_based_extract(
        "saya mau ainya ga basa basi dan langsung sat set. kebutuhan saya untuk ai ini adalah ngoding dan ngatur jadwal."
    )
    titles = {c.title for c in candidates}
    assert "Direct response style" in titles
    assert "AI usage needs" in titles
    assert all(c.confidence > 0.55 for c in candidates)


def test_extracts_broad_goal_for_direct_memory_save():
    candidates = rule_based_extract("saya mau website ini siap launching dan gampang diinstall.")
    assert len(candidates) == 1
    assert candidates[0].category == "Goals"
    assert "siap launching" in candidates[0].content
    assert candidates[0].confidence > 0.55


# --- schedule_extraction: auto-learning disabled --------------------------------


def test_schedule_extraction_disabled_returns_zero_and_writes_nothing(
    auth_client, db_session
):
    principal = _principal(auth_client)
    ai_settings_service.set_memory_settings(
        db_session, principal, {"auto_learning_enabled": False}
    )
    count = schedule_extraction(
        db_session, principal, "My name is Alice.", "Nice to meet you!", None
    )
    assert count == 0
    assert _memory_count(db_session, principal) == 0
    assert _suggestion_count(db_session, principal) == 0


# --- schedule_extraction: sync save path -----------------------------------------


def test_schedule_extraction_saves_low_sensitivity_high_confidence_as_memory(
    auth_client, db_session
):
    principal = _principal(auth_client)
    count = schedule_extraction(
        db_session, principal, "My name is Alice.", "Hello Alice!", None
    )
    assert count == 1
    memories = (
        db_session.query(AiMemory)
        .filter(AiMemory.workspace_id == principal.workspace_id)
        .all()
    )
    assert len(memories) == 1
    m = memories[0]
    assert m.category == "Profile"
    assert m.title == "User name"
    assert "Alice" in m.content
    assert m.source == "chat_extracted"
    assert _suggestion_count(db_session, principal) == 0


def test_high_sensitivity_candidate_becomes_suggestion_not_memory(
    auth_client, db_session
):
    principal = _principal(auth_client)
    candidate = MemoryCandidate(
        category="Profile",
        title="Health info",
        content="User has a chronic condition.",
        confidence=0.95,
        sensitivity="HIGH",
        snippet="saya punya kondisi kronis",
    )
    _auto_save_or_suggest(db_session, principal, candidate, None)
    db_session.flush()
    assert _memory_count(db_session, principal) == 0
    suggestions = (
        db_session.query(AiMemorySuggestion)
        .filter(AiMemorySuggestion.workspace_id == principal.workspace_id)
        .all()
    )
    assert len(suggestions) == 1
    assert suggestions[0].title == "Health info"
    assert suggestions[0].status == "pending"


def test_low_confidence_candidate_becomes_suggestion_not_memory(
    auth_client, db_session
):
    principal = _principal(auth_client)
    candidate = MemoryCandidate(
        category="Preferences",
        title="Vague preference",
        content="User maybe prefers dark mode.",
        confidence=0.5,
        sensitivity="LOW",
        snippet="mungkin dark mode",
    )
    _auto_save_or_suggest(db_session, principal, candidate, None)
    db_session.flush()
    assert _memory_count(db_session, principal) == 0
    assert _suggestion_count(db_session, principal) == 1


# --- schedule_extraction never raises ---------------------------------------------


def test_schedule_extraction_never_raises_on_broken_db(auth_client, tmp_path):
    principal = _principal(auth_client)
    # A session bound to an engine whose sqlite file cannot be opened: every
    # query raises OperationalError.
    bad_engine = create_engine(
        f"sqlite:///{tmp_path}/no-such-dir/broken.sqlite"
    )
    BadSession = sessionmaker(bind=bad_engine)
    bad_db = BadSession()
    try:
        count = schedule_extraction(
            bad_db, principal, "My name is Alice.", "Hi!", None
        )
        assert count == 0
    finally:
        bad_db.close()


def test_schedule_extraction_never_raises_on_invalid_session(auth_client):
    principal = _principal(auth_client)
    assert schedule_extraction(None, principal, "My name is Alice.", "Hi!", None) == 0


# --- LLM extraction (plan stubbed) -------------------------------------------------


class _StubPlan:
    def __init__(self, content, ok=True, runnable=True):
        self._content = content
        self._ok = ok
        self.runnable = runnable

    def execute(self, messages, params=None, tools=None):
        return SimpleNamespace(ok=self._ok, content=self._content, error="")


def test_llm_extract_parses_fenced_json_and_drops_secrets(
    auth_client, db_session, monkeypatch
):
    principal = _principal(auth_client)
    content = (
        "```json\n"
        '[{"category": "Technical", "title": "Editor", '
        '"content": "User uses Neovim.", "confidence": 0.85, "sensitivity": "LOW"},'
        '{"category": "Technical", "title": "Leaked key", '
        '"content": "api_key=sk-abc123DEF456ghi789", "confidence": 0.9, "sensitivity": "LOW"},'
        '{"category": "Profile", "title": "", '
        '"content": "Empty title gets dropped.", "confidence": 0.9, "sensitivity": "LOW"}]'
        "\n```"
    )
    monkeypatch.setattr(
        "app.services.ai_provider_router.plan_chat",
        lambda db, principal, provider_id=None, slot=1: _StubPlan(content),
    )
    candidates = _llm_extract_candidates(
        "I do all my editing in Neovim these days", "Good choice!", principal, db_session
    )
    assert len(candidates) == 1
    assert candidates[0].title == "Editor"
    assert candidates[0].content == "User uses Neovim."


def test_llm_extract_returns_empty_when_plan_not_runnable(
    auth_client, db_session, monkeypatch
):
    principal = _principal(auth_client)
    monkeypatch.setattr(
        "app.services.ai_provider_router.plan_chat",
        lambda db, principal, provider_id=None, slot=1: _StubPlan("", runnable=False),
    )
    assert (
        _llm_extract_candidates("some message", "some reply", principal, db_session)
        == []
    )


def test_llm_extract_returns_empty_when_auto_learning_disabled(
    auth_client, db_session, monkeypatch
):
    principal = _principal(auth_client)
    ai_settings_service.set_memory_settings(
        db_session, principal, {"auto_learning_enabled": False}
    )

    def _fail(*args, **kwargs):  # plan_chat must never be reached
        raise AssertionError("plan_chat should not be called when disabled")

    monkeypatch.setattr("app.services.ai_provider_router.plan_chat", _fail)
    assert (
        _llm_extract_candidates("some message", "some reply", principal, db_session)
        == []
    )


def test_llm_extract_returns_empty_on_malformed_json(
    auth_client, db_session, monkeypatch
):
    principal = _principal(auth_client)
    monkeypatch.setattr(
        "app.services.ai_provider_router.plan_chat",
        lambda db, principal, provider_id=None, slot=1: _StubPlan("not json at all"),
    )
    assert (
        _llm_extract_candidates("some message", "some reply", principal, db_session)
        == []
    )


# --- Fix 1: require_approval_sensitive wiring -----------------------------------


def test_require_approval_sensitive_on_medium_becomes_suggestion(
    auth_client, db_session
):
    """Default setting (ON): MEDIUM sensitivity candidate → suggestion, not memory."""
    principal = _principal(auth_client)
    # Default is ON — ensure it's explicitly set.
    ai_settings_service.set_memory_settings(
        db_session, principal, {"require_approval_sensitive": True}
    )
    candidate = MemoryCandidate(
        category="Profile",
        title="Work location",
        content="User works from home.",
        confidence=0.9,
        sensitivity="MEDIUM",
        snippet="saya kerja dari rumah",
    )
    _auto_save_or_suggest(db_session, principal, candidate, None)
    db_session.flush()
    assert _memory_count(db_session, principal) == 0
    assert _suggestion_count(db_session, principal) == 1


def test_require_approval_sensitive_off_medium_auto_saves(
    auth_client, db_session
):
    """Setting OFF: MEDIUM sensitivity + high confidence → auto-saved memory, not suggestion."""
    principal = _principal(auth_client)
    ai_settings_service.set_memory_settings(
        db_session, principal, {"require_approval_sensitive": False}
    )
    candidate = MemoryCandidate(
        category="Profile",
        title="Work location",
        content="User works from home.",
        confidence=0.9,
        sensitivity="MEDIUM",
        snippet="saya kerja dari rumah",
    )
    _auto_save_or_suggest(db_session, principal, candidate, None)
    db_session.flush()
    assert _memory_count(db_session, principal) == 1
    assert _suggestion_count(db_session, principal) == 0


def test_require_approval_sensitive_off_low_confidence_still_suggests(
    auth_client, db_session
):
    """Setting OFF: low-confidence candidate still becomes a suggestion (confidence gate is immutable)."""
    principal = _principal(auth_client)
    ai_settings_service.set_memory_settings(
        db_session, principal, {"require_approval_sensitive": False}
    )
    candidate = MemoryCandidate(
        category="Preferences",
        title="Uncertain preference",
        content="User might prefer light mode.",
        confidence=0.55,
        sensitivity="MEDIUM",
        snippet="mungkin light mode",
    )
    _auto_save_or_suggest(db_session, principal, candidate, None)
    db_session.flush()
    assert _memory_count(db_session, principal) == 0
    assert _suggestion_count(db_session, principal) == 1


# --- Fix 2: LLM extraction path hardening --------------------------------------


def test_llm_extract_skips_candidate_with_secret_in_title(
    auth_client, db_session, monkeypatch
):
    """A candidate whose *title* contains a secret is dropped."""
    principal = _principal(auth_client)
    content = (
        '[{"category": "Technical", "title": "sk-abc123DEF456ghi789", '
        '"content": "User exposed a key.", "confidence": 0.9, "sensitivity": "LOW"},'
        '{"category": "Profile", "title": "Safe title", '
        '"content": "User is Alice.", "confidence": 0.9, "sensitivity": "LOW"}]'
    )
    monkeypatch.setattr(
        "app.services.ai_provider_router.plan_chat",
        lambda db, principal, provider_id=None, slot=1: _StubPlan(content),
    )
    candidates = _llm_extract_candidates(
        "some message", "some reply", principal, db_session
    )
    assert len(candidates) == 1
    assert candidates[0].title == "Safe title"


def test_llm_extract_invalid_category_defaults_to_profile(
    auth_client, db_session, monkeypatch
):
    """An invalid or >50-char category from the model is replaced with 'Profile'."""
    principal = _principal(auth_client)
    bogus_category = "X" * 60  # way too long and not in MEMORY_CATEGORIES
    content = (
        f'[{{"category": "{bogus_category}", "title": "Some fact", '
        f'"content": "User fact here.", "confidence": 0.9, "sensitivity": "LOW"}}]'
    )
    monkeypatch.setattr(
        "app.services.ai_provider_router.plan_chat",
        lambda db, principal, provider_id=None, slot=1: _StubPlan(content),
    )
    candidates = _llm_extract_candidates(
        "some message", "some reply", principal, db_session
    )
    assert len(candidates) == 1
    assert candidates[0].category == "Profile"


def test_llm_path_records_extraction_method_llm(
    auth_client, db_session, monkeypatch
):
    """Candidates from the LLM path are stored as suggestions with extraction_method='llm'."""
    principal = _principal(auth_client)
    # Use MEDIUM sensitivity so it becomes a suggestion (default setting ON).
    content = (
        '[{"category": "Technical", "title": "IDE preference", '
        '"content": "User prefers VS Code.", "confidence": 0.85, "sensitivity": "MEDIUM"}]'
    )
    monkeypatch.setattr(
        "app.services.ai_provider_router.plan_chat",
        lambda db, principal, provider_id=None, slot=1: _StubPlan(content),
    )
    candidates = _llm_extract_candidates(
        "I use VS Code for everything", "Good choice!", principal, db_session
    )
    assert len(candidates) == 1
    _auto_save_or_suggest(
        db_session, principal, candidates[0], None, extraction_method="llm"
    )
    db_session.flush()
    suggestion = (
        db_session.query(AiMemorySuggestion)
        .filter(AiMemorySuggestion.workspace_id == principal.workspace_id)
        .one()
    )
    assert suggestion.extraction_method == "llm"


def test_llm_extract_invalid_sensitivity_defaults_to_medium(
    auth_client, db_session, monkeypatch
):
    """An unrecognised sensitivity value is replaced with MEDIUM (fail-safe: requires approval)."""
    principal = _principal(auth_client)
    content = (
        '[{"category": "Profile", "title": "Some fact", '
        '"content": "User fact here.", "confidence": 0.9, "sensitivity": "UNKNOWN"}]'
    )
    monkeypatch.setattr(
        "app.services.ai_provider_router.plan_chat",
        lambda db, principal, provider_id=None, slot=1: _StubPlan(content),
    )
    candidates = _llm_extract_candidates(
        "some message", "some reply", principal, db_session
    )
    assert len(candidates) == 1
    assert candidates[0].sensitivity == "MEDIUM"
