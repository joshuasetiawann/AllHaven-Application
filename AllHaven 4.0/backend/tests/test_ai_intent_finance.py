"""3.9 AI intent routing + finance tooling + memory-gating tests.

- Indonesian money phrases parse correctly and route to a finance PROPOSAL.
- Finance/transaction messages NEVER become memory.
- Explicit "ingat bahwa ..." routes to memory.
- Finance proposals create a PENDING approval with category_id null (not "").
"""
import uuid

import pytest

from app.core.principal import Principal
from app.domain.ai import AiToolProposal
from app.domain.ai_memory import AiMemory, AiMemorySuggestion
from app.services import ai_intent_router as router
from app.services.ai_tools_registry import normalize_tool_payload
from app.services.memory_extraction_service import _should_skip_memory, schedule_extraction
from tests.conftest import API


# --------------------------- pure intent router ---------------------------- #

@pytest.mark.parametrize("raw,expected", [
    ("500 ribu", 500_000), ("50rb", 50_000), ("1 juta", 1_000_000),
    ("1.5 juta", 1_500_000), ("1,5 juta", 1_500_000), ("Rp 100.000", 100_000),
    ("100000", 100_000), ("Rp1.000.000", 1_000_000), ("2jt", 2_000_000),
    ("250 ribu", 250_000), ("abc", None),
])
def test_parse_idr_amount(raw, expected):
    assert router.parse_idr_amount(raw) == expected


def test_income_phrase_routes_to_finance_not_memory():
    res = router.classify("saya dapat pendapatan 500 ribu")
    assert res.intent == router.FINANCE
    assert res.txn_type == "INCOME"
    assert res.amount == 500_000


def test_expense_phrase_routes_to_finance():
    res = router.classify("catat pengeluaran makan 50 ribu")
    assert res.intent == router.FINANCE
    assert res.txn_type == "EXPENSE"
    assert res.amount == 50_000


def test_project_income_description():
    res = router.classify("saya dapat project 500 ribu")
    assert res.intent == router.FINANCE and res.txn_type == "INCOME"
    assert res.description.lower() == "project"


def test_explicit_remember_routes_to_memory():
    assert router.classify("ingat bahwa saya lebih suka UI gelap").intent == router.MEMORY


def test_plain_chat_is_general():
    assert router.classify("halo apa kabar").intent == router.GENERAL
    assert router.classify("umur saya 25 tahun").intent == router.GENERAL


@pytest.mark.parametrize("raw,expected", [
    ("2.500 ribu", 2_500_000),   # grouping dot before a multiplier (was 2500)
    ("10.000 ribu", 10_000_000),
    ("50k", 50_000),
])
def test_parse_grouping_and_attached_k(raw, expected):
    assert router.parse_idr_amount(raw) == expected


@pytest.mark.parametrize("msg", [
    "beli 3 buku",          # 'b' of buku must NOT become a billion multiplier
    "beli 5 mangga",
    "tahun 2024",           # a year is not money
    "nomor saya 081234567890",  # phone number is not money
    "pin 123456",
    "lari 5 km",
])
def test_non_money_messages_are_not_finance(msg):
    assert router.classify(msg).intent != router.FINANCE


def test_bare_amount_with_verb_is_finance():
    res = router.classify("gaji 5000000")
    assert res.intent == router.FINANCE and res.txn_type == "INCOME" and res.amount == 5_000_000


def test_multiple_amounts_request_clarification():
    res = router.classify("gaji 5jt sama bonus 1jt")
    assert res.intent == router.FINANCE and res.needs_clarification is True


# ------------------------- normalize finance payload ----------------------- #

def test_normalize_finance_parses_amount_and_nulls_category():
    out = normalize_tool_payload("create_transaction", {
        "type": "INCOME", "amount": "500 ribu", "category_id": "", "description": "",
    })
    assert out["amount"] == 500_000
    assert out["category_id"] is None          # never "" — spec rule
    assert out["currency"] == "IDR"
    assert out["transaction_date"]             # defaulted to today
    assert out["description"]                   # synthesized, not empty


def test_normalize_infers_type_from_description():
    out = normalize_tool_payload("create_transaction", {"amount": 50000, "description": "belanja sayur"})
    assert out["type"] == "EXPENSE"


# ----------------------------- memory gating ------------------------------- #

def test_should_skip_memory_for_finance_and_greeting():
    assert _should_skip_memory("saya dapat pendapatan 500 ribu") is True
    assert _should_skip_memory("catat pengeluaran makan 50 ribu") is True
    assert _should_skip_memory("halo") is True
    assert _should_skip_memory("ingat bahwa saya suka kopi") is False  # explicit memory survives


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def test_finance_message_does_not_create_memory(auth_client, db_session):
    principal = _principal(auth_client)
    schedule_extraction(
        db_session, principal,
        user_msg="saya dapat pendapatan 500 ribu",
        assistant_msg="Saya buatkan draft pendapatan Rp500.000.",
        session_id=None,
    )
    db_session.flush()
    mem = db_session.query(AiMemory).filter(AiMemory.workspace_id == principal.workspace_id).count()
    sug = db_session.query(AiMemorySuggestion).filter(
        AiMemorySuggestion.workspace_id == principal.workspace_id).count()
    assert mem == 0 and sug == 0


# -------------------- finance message -> pending proposal ------------------ #

def test_finance_chat_creates_pending_proposal(auth_client, db_session):
    principal = _principal(auth_client)
    resp = auth_client.post(f"{API}/ai/chat", json={"message": "saya dapat pendapatan 500 ribu"})
    assert resp.status_code == 200, resp.text
    content = resp.json()["data"]["reply"]["content"]
    # Human-readable summary, never a bare "completed".
    assert "draft" in content.lower()
    assert "500.000" in content

    props = db_session.query(AiToolProposal).filter(
        AiToolProposal.workspace_id == principal.workspace_id,
        AiToolProposal.status == "PENDING",
    ).all()
    assert len(props) >= 1
    p = [x for x in props if x.tool_name in (
        "create_transaction", "create_transaction_draft")][0]
    assert p.tool_payload["type"] == "INCOME"
    assert p.tool_payload["amount"] == 500_000
    assert p.tool_payload.get("category_id") is None  # null, never ""


def test_failed_proposal_stays_visible(auth_client, db_session):
    """A NEEDS_EDIT/FAILED proposal must NOT disappear from the pending list (3.9)."""
    from app.services import ai_service

    principal = _principal(auth_client)
    p = AiToolProposal(
        workspace_id=principal.workspace_id, created_by=principal.user_id,
        tool_name="create_transaction",
        tool_payload={"type": "INCOME", "amount": 1000, "currency": "IDR"},
        status="NEEDS_EDIT", error_message="boom", risk_level="MEDIUM",
    )
    db_session.add(p)
    db_session.commit()
    listed = ai_service.list_proposals(db_session, principal)
    assert any(x.id == p.id for x in listed)

