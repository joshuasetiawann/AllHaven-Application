"""Regression tests for durable, sync-safe AI memory deletes (the user-reported
"I delete a memory, refresh, and it comes back" bug).

A delete must be a soft-delete (is_deleted=True) so the two-way sync engine carries it
as an UPDATE instead of the row being resurrected from the peer; all reads must exclude
it; and background extraction must not re-learn a memory the user deleted.
"""
import uuid

from app.core.principal import Principal
from app.domain.ai_memory import AiMemory
from app.services import memory_service
from app.services.memory_extraction_service import _auto_save_or_suggest, MemoryCandidate
from tests.conftest import API


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def test_delete_is_soft_and_durable(auth_client, db_session):
    principal = _principal(auth_client)
    m = memory_service.create_memory(
        db_session, principal, category="Profile", title="Suka kopi", content="User suka kopi",
    )
    mid = m.id
    db_session.commit()

    memory_service.delete_memory(db_session, principal, mid)
    db_session.commit()

    # Row still exists (soft delete) so sync can carry the tombstone — but flagged deleted.
    row = db_session.get(AiMemory, mid)
    assert row is not None
    assert row.is_deleted is True
    assert row.deleted_at is not None
    assert row.enabled is False

    # Excluded from every read path.
    assert all(x.id != mid for x in memory_service.list_memories(db_session, principal))
    assert all(x.id != mid for x in memory_service.search_memories(db_session, principal, "kopi"))


def test_extraction_does_not_relearn_a_deleted_memory(auth_client, db_session):
    principal = _principal(auth_client)
    m = memory_service.create_memory(
        db_session, principal, category="Profile", title="Nama panggilan Joo", content="Panggil Joo",
    )
    mid = m.id
    memory_service.delete_memory(db_session, principal, mid)
    db_session.commit()

    # Background extraction tries to save the SAME fact (same category+title).
    cand = MemoryCandidate(
        category="Profile", title="Nama panggilan Joo", content="Panggil Joo",
        snippet="panggil saya Joo", confidence=0.95, sensitivity="LOW", explicit=False,
    )
    _auto_save_or_suggest(db_session, principal, cand, session_id=None)
    db_session.commit()

    # The deleted memory stays deleted; no active twin and no pending suggestion appear.
    assert all(not x.is_deleted for x in memory_service.list_memories(db_session, principal))
    active = [x for x in db_session.query(AiMemory).filter(
        AiMemory.workspace_id == principal.workspace_id, AiMemory.is_deleted == False).all()]  # noqa: E712
    assert all(x.id != mid for x in active)
    assert len(memory_service.list_suggestions(db_session, principal)) == 0


def test_manual_upsert_can_revive_a_deleted_memory(auth_client, db_session):
    principal = _principal(auth_client)
    m = memory_service.create_memory(
        db_session, principal, category="Preferences", title="Tema gelap", content="Suka dark mode",
    )
    memory_service.delete_memory(db_session, principal, m.id)
    db_session.commit()

    # An explicit (manual) re-add is allowed to revive it.
    revived = memory_service.upsert_memory(
        db_session, principal, category="Preferences", title="Tema gelap",
        content="Suka dark mode lagi", source="manual",
    )
    db_session.commit()
    assert revived.is_deleted is False
    assert revived.enabled is True
    assert any(x.id == revived.id for x in memory_service.list_memories(db_session, principal))
