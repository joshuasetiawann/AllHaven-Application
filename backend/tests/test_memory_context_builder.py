"""Tests for memory_context_builder: composing memories into a compact context block.

Covers: memory recall with auto-learning on/off, always-include categories,
keyword-gated Projects inclusion, section-key category mapping, message keyword
search, dedup across selection sources, mark-used side effects, per-memory
content capping, and whole-block truncation.
"""

import uuid
from datetime import datetime, timezone

from app.core.principal import Principal
from app.services import ai_settings_service, memory_context_builder, memory_service
from tests.conftest import API


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def _create(db, principal, *, category, title, content, **kwargs):
    return memory_service.create_memory(
        db, principal, category=category, title=title, content=content, **kwargs
    )


# --- empty / disabled gates ----------------------------------------------------


def test_build_returns_none_when_no_memories(auth_client, db_session):
    principal = _principal(auth_client)
    assert memory_context_builder.build(db_session, principal, "hello there") is None


def test_build_still_recalls_existing_memories_when_auto_learning_disabled(auth_client, db_session):
    principal = _principal(auth_client)
    _create(db_session, principal, category="Profile", title="Name", content="Joshua")
    ai_settings_service.set_memory_settings(
        db_session, principal, {"auto_learning_enabled": False}
    )
    block = memory_context_builder.build(db_session, principal, "hello there")
    assert block is not None
    assert "Joshua" in block


# --- always-include categories ---------------------------------------------------


def test_build_always_includes_profile_and_preferences(auth_client, db_session):
    principal = _principal(auth_client)
    _create(db_session, principal, category="Profile", title="Name", content="Joshua dari Jakarta")
    _create(db_session, principal, category="Preferences", title="Lang", content="Replies in Indonesian")
    block = memory_context_builder.build(db_session, principal, "hello there")
    assert block is not None
    assert block.startswith("[AI Memory - user context, use when relevant]")
    assert block.rstrip().endswith("[End of memory context]")
    assert "Profile:" in block
    assert "Joshua dari Jakarta" in block
    assert "Preferences:" in block
    assert "Replies in Indonesian" in block


def test_build_excludes_disabled_and_inactive_memories(auth_client, db_session):
    principal = _principal(auth_client)
    enabled = _create(db_session, principal, category="Profile", title="Keep", content="keep me")
    disabled = _create(db_session, principal, category="Profile", title="Off", content="disabled memory")
    disabled.enabled = False
    stale = _create(db_session, principal, category="Preferences", title="Old", content="stale memory")
    stale.status = "stale"
    db_session.flush()

    block = memory_context_builder.build(db_session, principal, "hello there")
    assert block is not None
    assert enabled.content in block
    assert "disabled memory" not in block
    assert "stale memory" not in block


# --- conditional Projects inclusion ------------------------------------------------


def test_build_includes_projects_for_project_related_message(auth_client, db_session):
    principal = _principal(auth_client)
    _create(db_session, principal, category="Profile", title="Name", content="Joshua")
    _create(db_session, principal, category="Projects", title="AllHaven", content="Working on AllHaven")
    block = memory_context_builder.build(db_session, principal, "how is my project going?")
    assert block is not None
    assert "Working on AllHaven" in block


def test_build_can_include_ranked_projects_for_unrelated_message(auth_client, db_session):
    principal = _principal(auth_client)
    _create(db_session, principal, category="Profile", title="Name", content="Joshua")
    _create(db_session, principal, category="Projects", title="AllHaven", content="Working on AllHaven")
    block = memory_context_builder.build(db_session, principal, "what should I eat today?")
    assert block is not None
    assert "Working on AllHaven" in block


# --- section-specific inclusion -------------------------------------------------------


def test_build_includes_mapped_category_for_section(auth_client, db_session):
    principal = _principal(auth_client)
    _create(db_session, principal, category="Profile", title="Name", content="Joshua")
    _create(db_session, principal, category="Goals", title="Saving", content="Save 20 percent monthly")
    block = memory_context_builder.build(
        db_session, principal, "hello there", section_key="finance"
    )
    assert block is not None
    assert "Save 20 percent monthly" in block


def test_build_general_section_can_include_ranked_mapped_categories(auth_client, db_session):
    principal = _principal(auth_client)
    _create(db_session, principal, category="Profile", title="Name", content="Joshua")
    _create(db_session, principal, category="Goals", title="Saving", content="Save 20 percent monthly")
    block = memory_context_builder.build(
        db_session, principal, "hello there", section_key="general"
    )
    assert block is not None
    assert "Save 20 percent monthly" in block


# --- message keyword search -----------------------------------------------------------


def test_build_includes_memories_matching_message_keywords(auth_client, db_session):
    principal = _principal(auth_client)
    _create(db_session, principal, category="Profile", title="Name", content="Joshua")
    _create(db_session, principal, category="Technical", title="K8s", content="Prefers kubernetes for orchestration")
    block = memory_context_builder.build(db_session, principal, "kubernetes")
    assert block is not None
    assert "Prefers kubernetes for orchestration" in block


def test_build_dedups_memory_matched_by_multiple_sources(auth_client, db_session):
    principal = _principal(auth_client)
    # Matched both as always-include (Profile) and by the message keyword search.
    _create(db_session, principal, category="Profile", title="Name", content="Joshua loves kubernetes")
    block = memory_context_builder.build(db_session, principal, "kubernetes")
    assert block is not None
    assert block.count("Joshua loves kubernetes") == 1


def test_build_uses_latest_single_value_profile_fact(auth_client, db_session):
    principal = _principal(auth_client)
    old = _create(
        db_session,
        principal,
        category="Profile",
        title="User partner",
        content="User's partner is Frecil.",
    )
    new = _create(
        db_session,
        principal,
        category="Profile",
        title="User partner",
        content="User's partner is Kelly.",
    )
    old.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    new.updated_at = datetime(2026, 6, 27, tzinfo=timezone.utc)
    db_session.flush()

    block = memory_context_builder.build(db_session, principal, "siapa pacar saya?")

    assert block is not None
    assert "Kelly" in block
    assert "Frecil" not in block


# --- usage tracking ----------------------------------------------------------------


def test_build_marks_selected_memories_as_used(auth_client, db_session):
    principal = _principal(auth_client)
    m = _create(db_session, principal, category="Profile", title="Name", content="Joshua")
    assert m.last_used_at is None
    score_before = m.relevance_score
    block = memory_context_builder.build(db_session, principal, "hello there")
    assert block is not None
    db_session.refresh(m)
    assert m.last_used_at is not None
    assert m.relevance_score > score_before


# --- size limits --------------------------------------------------------------------


def test_build_caps_content_per_memory(auth_client, db_session):
    principal = _principal(auth_client)
    long_content = "x" * (memory_context_builder.MAX_CONTENT_PER_MEMORY + 100)
    _create(db_session, principal, category="Profile", title="Long", content=long_content)
    block = memory_context_builder.build(db_session, principal, "hello there")
    assert block is not None
    assert "x" * memory_context_builder.MAX_CONTENT_PER_MEMORY in block
    assert long_content not in block


def test_build_truncates_oversized_block(auth_client, db_session):
    principal = _principal(auth_client)
    for i in range(15):
        _create(
            db_session, principal,
            category="Profile", title=f"Memory {i}",
            content=f"memory {i} " + "y" * memory_context_builder.MAX_CONTENT_PER_MEMORY,
        )
    block = memory_context_builder.build(db_session, principal, "hello there")
    assert block is not None
    assert block.endswith("[Memory truncated to fit context limit]")
    assert len(block) <= memory_context_builder.MAX_BLOCK_CHARS + len(
        "\n[Memory truncated to fit context limit]"
    )
