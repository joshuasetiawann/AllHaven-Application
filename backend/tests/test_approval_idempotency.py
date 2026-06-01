"""Cross-device approval idempotency: a proposal executes at most once.

Once executed (here, or — after LWW sync — on the other device, signalled by a
non-null executed_at), a second approve is blocked with a 409 instead of creating a
duplicate record. executed_by + target_entity_id are recorded.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ConflictError
from app.core.principal import Principal
from app.domain.ai import AiToolProposal
from app.services.ai_tools_registry import approve_proposal
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


def test_first_approve_executes_and_records_metadata(auth_client, db_session):
    principal = _principal(auth_client)
    p = _pending_finance(auth_client, db_session)
    approve_proposal(db_session, principal, p.id)
    db_session.refresh(p)
    assert p.status == "EXECUTED"
    assert p.executed_at is not None
    assert p.executed_by == principal.user_id
    assert p.target_entity_id is not None          # the created transaction's id


def test_second_approve_is_blocked_with_409(auth_client, db_session):
    principal = _principal(auth_client)
    p = _pending_finance(auth_client, db_session)
    approve_proposal(db_session, principal, p.id)          # device 1
    with pytest.raises(ConflictError):                     # device 2, after sync
        approve_proposal(db_session, principal, p.id)


def test_executed_marker_blocks_even_when_status_lags(auth_client, db_session):
    # Cross-device: executed_at synced over but status not yet -> must still block.
    principal = _principal(auth_client)
    p = AiToolProposal(
        workspace_id=principal.workspace_id, created_by=principal.user_id,
        tool_name="create_transaction",
        tool_payload={"type": "EXPENSE", "amount": 1000, "currency": "IDR"},
        status="PENDING", risk_level="MEDIUM",
        executed_at=datetime.now(timezone.utc),
    )
    db_session.add(p)
    db_session.commit()
    with pytest.raises(ConflictError):
        approve_proposal(db_session, principal, p.id)


def test_failed_proposal_still_re_approvable(auth_client, db_session):
    # A NEEDS_EDIT/FAILED proposal (never executed) is NOT blocked by the new gate.
    principal = _principal(auth_client)
    p = _pending_finance(auth_client, db_session)
    p.status = "NEEDS_EDIT"
    p.error_message = "boom"
    db_session.commit()
    approve_proposal(db_session, principal, p.id)          # executed_at None -> proceeds
    db_session.refresh(p)
    assert p.status == "EXECUTED"
