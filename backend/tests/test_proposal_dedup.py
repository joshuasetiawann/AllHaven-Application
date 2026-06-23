"""Pre-sync race hardening: a proposal-scoped dedup_key stops the rare window where
BOTH devices approve the same proposal before executed_at syncs and each inserts a
duplicate finance/routine row.

The executor stamps every produced entity with ``dedup_key = f"{proposal_id}:{ordinal}"``
(deterministic + identical on desktop and mobile). On sync, lww_apply skips inserting a
row whose dedup_key already exists locally under a different PK, so the two devices'
rows converge to one entity instead of duplicating.
"""
import uuid
from datetime import datetime, timezone

from app.core.principal import Principal
from app.domain.ai import AiToolProposal
from app.domain.calendar import CalendarEvent
from app.domain.finance import FinanceCategory, Transaction
from app.services import sync_engine, sync_registry
from app.services.ai_tools_registry import approve_proposal
from app.core.database import SessionLocal
from tests.conftest import API


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def _pending_finance(auth_client, db_session) -> AiToolProposal:
    auth_client.post(f"{API}/ai/chat", json={"message": "catat pengeluaran makan 50 ribu"})
    principal = _principal(auth_client)
    return db_session.query(AiToolProposal).filter(
        AiToolProposal.workspace_id == principal.workspace_id,
        AiToolProposal.tool_name == "create_transaction",
        AiToolProposal.status == "PENDING",
    ).one()


def test_approve_transaction_stamps_proposal_scoped_dedup_key(auth_client, db_session):
    principal = _principal(auth_client)
    p = _pending_finance(auth_client, db_session)
    approve_proposal(db_session, principal, p.id)
    db_session.refresh(p)
    tx = db_session.get(Transaction, p.target_entity_id)
    assert tx is not None
    assert tx.dedup_key == f"{p.id}:0"


def test_approve_transaction_resolves_category_name_to_uuid(auth_client, db_session):
    """The model often drafts category_id as a human label ("makan"). Approval should
    resolve/create the category instead of failing Pydantic UUID validation."""
    principal = _principal(auth_client)
    p = AiToolProposal(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        tool_name="create_transaction",
        risk_level="MEDIUM",
        status="PENDING",
        tool_payload={
            "type": "EXPENSE",
            "amount": 150000,
            "category_id": "makan",
            "description": "Makan",
            "transaction_date": "2026-06-23",
        },
    )
    db_session.add(p)
    db_session.commit()

    approve_proposal(db_session, principal, p.id)
    db_session.refresh(p)

    tx = db_session.get(Transaction, p.target_entity_id)
    assert tx is not None
    assert tx.category_id is not None
    assert tx.category_name_snapshot == "makan"
    category = db_session.get(FinanceCategory, tx.category_id)
    assert category is not None
    assert category.name == "makan"
    assert category.type == "EXPENSE"


def test_approve_routine_schedule_stamps_distinct_dedup_keys(auth_client, db_session):
    principal = _principal(auth_client)
    p = AiToolProposal(
        workspace_id=principal.workspace_id, created_by=principal.user_id,
        tool_name="create_routine_schedule", risk_level="LOW", status="PENDING",
        tool_payload={
            "blocks": [{"title": "Olahraga", "start_time": "06:00", "duration_min": 30}],
            "repeat_days": 2, "start_date": "2026-06-22",
        },
    )
    db_session.add(p)
    db_session.commit()
    approve_proposal(db_session, principal, p.id)
    events = db_session.query(CalendarEvent).filter(
        CalendarEvent.workspace_id == principal.workspace_id
    ).all()
    keys = sorted(e.dedup_key for e in events)
    assert keys == [f"{p.id}:0", f"{p.id}:1"]


def test_lww_apply_skips_row_whose_dedup_key_already_exists_locally():
    """The core cross-device guard: device B's row (same proposal, different PK) must
    NOT create a second calendar_event when device A's row is already present."""
    db = SessionLocal()
    try:
        ws = uuid.uuid4()
        user = uuid.uuid4()
        proposal_id = uuid.uuid4()
        dedup = f"{proposal_id}:0"
        local = CalendarEvent(
            id=uuid.uuid4(), workspace_id=ws, created_by=user, title="A's event",
            start_at=datetime(2026, 6, 22, 6, 0, tzinfo=timezone.utc), dedup_key=dedup,
            updated_at=datetime(2026, 6, 22, tzinfo=timezone.utc),
        )
        db.add(local)
        db.commit()

        spec = sync_registry.spec_for("calendar_events")
        peer_row = {
            "id": str(uuid.uuid4()),  # different PK — device B's copy
            "workspace_id": str(ws), "created_by": str(user), "title": "B's event",
            "start_at": "2026-06-22T06:00:00+00:00", "dedup_key": dedup,
            "is_deleted": False, "created_at": "2026-06-22T00:00:00+00:00",
            "updated_at": "2026-06-22T00:00:01+00:00",
        }
        applied = sync_engine.lww_apply(db, spec, peer_row)
        db.commit()

        assert applied is None  # skipped, not inserted
        rows = db.query(CalendarEvent).filter(CalendarEvent.dedup_key == dedup).all()
        assert len(rows) == 1  # no duplicate
        assert rows[0].title == "A's event"
    finally:
        db.close()
