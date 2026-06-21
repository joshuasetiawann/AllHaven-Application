"""Approval execution for AI-created finance transactions.

Regression coverage for the bug where a create_transaction proposal carried
``category_id: ""`` (the model's stand-in for "no category"). Pydantic can't
parse ``""`` as a UUID, so approval failed on an otherwise valid action. The
registry now normalizes the payload before validation/execution: empty reference
ids become ``None`` and an empty transaction_date defaults to today.
"""

import uuid
from datetime import date

from app.core.principal import Principal
from app.services import ai_tools_registry
from app.services.ai_tools_registry import normalize_tool_payload
from tests.conftest import API


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def _transactions(auth_client) -> list[dict]:
    return auth_client.get(f"{API}/finance/transactions").json()["data"]


# --- normalization unit ----------------------------------------------------


def test_normalize_empty_reference_ids_become_none():
    out = normalize_tool_payload(
        "create_transaction",
        {"type": "EXPENSE", "amount": 100000, "category_id": "", "task_id": "", "note_id": ""},
    )
    assert out["category_id"] is None
    assert out["task_id"] is None
    assert out["note_id"] is None
    # A real id is left untouched.
    rid = str(uuid.uuid4())
    assert normalize_tool_payload("update_transaction", {"transaction_id": rid})["transaction_id"] == rid


def test_normalize_empty_transaction_date_defaults_today():
    out = normalize_tool_payload("create_transaction", {"type": "EXPENSE", "amount": 1, "transaction_date": ""})
    assert out["transaction_date"]  # not empty
    # Valid ISO date.
    assert date.fromisoformat(out["transaction_date"])


def test_normalize_is_pure_and_idempotent():
    payload = {"type": "EXPENSE", "amount": 1, "category_id": ""}
    once = normalize_tool_payload("create_transaction", payload)
    twice = normalize_tool_payload("create_transaction", once)
    assert payload["category_id"] == ""  # original untouched
    assert once["category_id"] is None and twice["category_id"] is None


# --- end-to-end approval ---------------------------------------------------


def _propose_transaction(auth_client, db_session, **overrides) -> str:
    principal = _principal(auth_client)
    payload = {
        "type": "EXPENSE",
        "amount": 100000,
        "currency": "IDR",
        "category_id": "",
        "description": "Pengeluaran",
        "transaction_date": "",
        **overrides,
    }
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "create_transaction", payload)
    db_session.commit()
    assert outcome["status"] == "pending_approval", outcome
    return outcome["proposal_id"]


def test_approve_transaction_with_empty_category_id_succeeds(auth_client, db_session):
    """The exact broken payload from the screenshot now approves cleanly."""
    pid = _propose_transaction(auth_client, db_session)
    resp = auth_client.post(f"{API}/ai/proposals/{pid}/approve")
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["proposal"]["status"] == "EXECUTED"
    txn = body["result"]["transaction"]
    assert txn["category_id"] is None
    assert txn["amount"] == 100000
    assert txn["transaction_date"]  # defaulted, not empty
    # Persisted with a null category (no "Uncategorized" row invented server-side).
    rows = _transactions(auth_client)
    assert any(t["category_id"] is None and t["amount"] == 100000 for t in rows)


def test_approve_transaction_with_explicit_null_category(auth_client, db_session):
    pid = _propose_transaction(auth_client, db_session, category_id=None)
    resp = auth_client.post(f"{API}/ai/proposals/{pid}/approve")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["result"]["transaction"]["category_id"] is None


def test_invalid_category_uuid_keeps_proposal_pending(auth_client, db_session):
    """A genuinely malformed id is blocked; the proposal stays editable, nothing created."""
    pid = _propose_transaction(auth_client, db_session, category_id="not-a-uuid")
    resp = auth_client.post(f"{API}/ai/proposals/{pid}/approve")
    assert resp.status_code == 422, resp.text
    # Proposal NOT marked executed — still in the pending list.
    pending = auth_client.get(f"{API}/ai/proposals").json()["data"]
    assert any(p["id"] == pid for p in pending)
    # No transaction was created.
    assert _transactions(auth_client) == []


def test_approve_is_idempotent_no_duplicate_transaction(auth_client, db_session):
    pid = _propose_transaction(auth_client, db_session)
    assert auth_client.post(f"{API}/ai/proposals/{pid}/approve").status_code == 200
    # A retry on an already-executed proposal is blocked with 409 (already executed),
    # never re-run — so no duplicate transaction across devices.
    assert auth_client.post(f"{API}/ai/proposals/{pid}/approve").status_code == 409
    rows = [t for t in _transactions(auth_client) if t["amount"] == 100000]
    assert len(rows) == 1


def test_edit_then_approve_normalizes_edited_payload(auth_client, db_session):
    """User edits to '' are normalized too, so a corrected proposal still approves."""
    pid = _propose_transaction(auth_client, db_session)
    resp = auth_client.patch(
        f"{API}/ai/proposals/{pid}",
        json={"tool_payload": {"type": "INCOME", "amount": 250, "category_id": "", "transaction_date": ""}},
    )
    assert resp.status_code == 200, resp.text
    resp = auth_client.post(f"{API}/ai/proposals/{pid}/approve")
    assert resp.status_code == 200, resp.text
    txn = resp.json()["data"]["result"]["transaction"]
    assert txn["type"] == "INCOME" and txn["category_id"] is None
