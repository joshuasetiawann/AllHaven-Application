"""Tests for memory_service dedup, sensitivity escalation, suggestion cap, and search escaping.

Covers the code-review fixes: SQL-side dedup (no 50-row scan window), sensitivity
escalation on upsert (never downgrade), the pending-suggestion quota, category-scoped
case-insensitive suggestion dedup, and LIKE-wildcard escaping in search.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ValidationAppError
from app.core.principal import Principal
from app.domain.ai_memory import AiMemory, AiMemorySuggestion
from app.services import memory_service
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


# --- dedup beyond the old 50-row window --------------------------------------


def test_upsert_dedups_beyond_50_memories_in_category(auth_client, db_session):
    principal = _principal(auth_client)
    memories = [
        memory_service.create_memory(
            db_session, principal,
            category="Technical", title=f"Memory {i}", content=f"content {i}",
        )
        for i in range(55)
    ]
    # Make the first memory the oldest by updated_at so it falls outside the
    # 50-row window the old Python-side scan used.
    memories[0].updated_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db_session.flush()
    assert _memory_count(db_session, principal) == 55

    result = memory_service.upsert_memory(
        db_session, principal,
        category="Technical", title="Memory 0", content="updated content",
    )
    assert result.id == memories[0].id
    assert result.content == "updated content"
    assert _memory_count(db_session, principal) == 55  # no duplicate row


# --- sensitivity escalation on upsert -----------------------------------------


def test_upsert_escalates_sensitivity_low_to_high(auth_client, db_session):
    principal = _principal(auth_client)
    created = memory_service.create_memory(
        db_session, principal,
        category="Profile", title="Health info", content="v1", sensitivity="LOW",
    )
    updated = memory_service.upsert_memory(
        db_session, principal,
        category="Profile", title="Health info", content="v2", sensitivity="HIGH",
    )
    assert updated.id == created.id
    assert updated.sensitivity == "HIGH"


def test_upsert_never_downgrades_sensitivity(auth_client, db_session):
    principal = _principal(auth_client)
    created = memory_service.create_memory(
        db_session, principal,
        category="Profile", title="Health info", content="v1", sensitivity="HIGH",
    )
    updated = memory_service.upsert_memory(
        db_session, principal,
        category="Profile", title="Health info", content="v2", sensitivity="LOW",
    )
    assert updated.id == created.id
    assert updated.sensitivity == "HIGH"


# --- pending suggestion cap ----------------------------------------------------


def test_pending_suggestion_limit_enforced(auth_client, db_session):
    principal = _principal(auth_client)
    for i in range(memory_service.MAX_SUGGESTIONS_PENDING):
        memory_service.create_suggestion(
            db_session, principal,
            category="Preferences", title=f"Suggestion {i}", content=f"content {i}",
            source_session_id=None, source_snippet="snippet",
            confidence=0.9, sensitivity="LOW",
        )
    with pytest.raises(ValidationAppError):
        memory_service.create_suggestion(
            db_session, principal,
            category="Preferences", title="One too many", content="content",
            source_session_id=None, source_snippet="snippet",
            confidence=0.9, sensitivity="LOW",
        )


# --- suggestion dedup semantics --------------------------------------------------


def test_suggestion_dedup_is_category_scoped(auth_client, db_session):
    principal = _principal(auth_client)
    first = memory_service.create_suggestion(
        db_session, principal,
        category="Profile", title="Same Title", content="a",
        source_session_id=None, source_snippet="s",
        confidence=0.9, sensitivity="LOW",
    )
    other_category = memory_service.create_suggestion(
        db_session, principal,
        category="Preferences", title="Same Title", content="b",
        source_session_id=None, source_snippet="s",
        confidence=0.9, sensitivity="LOW",
    )
    assert other_category.id != first.id
    count = (
        db_session.query(AiMemorySuggestion)
        .filter(AiMemorySuggestion.workspace_id == principal.workspace_id)
        .count()
    )
    assert count == 2


def test_suggestion_dedup_case_insensitive_within_category(auth_client, db_session):
    principal = _principal(auth_client)
    first = memory_service.create_suggestion(
        db_session, principal,
        category="Profile", title="Same Title", content="a",
        source_session_id=None, source_snippet="s",
        confidence=0.9, sensitivity="LOW",
    )
    duplicate = memory_service.create_suggestion(
        db_session, principal,
        category="Profile", title="  same title ", content="b",
        source_session_id=None, source_snippet="s",
        confidence=0.9, sensitivity="LOW",
    )
    assert duplicate.id == first.id
    count = (
        db_session.query(AiMemorySuggestion)
        .filter(AiMemorySuggestion.workspace_id == principal.workspace_id)
        .count()
    )
    assert count == 1


# --- search wildcard escaping -----------------------------------------------------


def test_search_escapes_like_wildcards(auth_client, db_session):
    principal = _principal(auth_client)
    memory_service.create_memory(
        db_session, principal,
        category="Technical", title="Alpha", content="some content",
    )
    assert memory_service.search_memories(db_session, principal, "%") == []
    # Sanity: normal search still works.
    found = memory_service.search_memories(db_session, principal, "alpha")
    assert len(found) == 1 and found[0].title == "Alpha"
