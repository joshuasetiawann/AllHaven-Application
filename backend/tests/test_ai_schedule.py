"""P1: deterministic schedule parser + create_routine_schedule.

Fixes the "atur jadwal 7 hari ..." -> one giant all-day event bug by turning a
routine request into structured, non-overlapping, timed per-day blocks under ONE
reviewable approval that expands across N days on approve.
"""
import uuid

import pytest

from app.core.principal import Principal
from app.domain.ai import AiToolProposal
from app.domain.ai_memory import AiMemory, AiMemorySuggestion
from app.domain.calendar import CalendarEvent
from app.services import schedule_parser
from app.services.ai_tools_registry import approve_proposal
from app.services.memory_extraction_service import _should_skip_memory, schedule_extraction
from tests.conftest import API

_CANONICAL = (
    "tolong atur jadwal saya untuk 7 hari kedepan, pagi nya mau jogging dulu, "
    "sarapan, baca buku, siang gym, belajar, kerja malam ngoding ya"
)


# ------------------------------ pure parser -------------------------------- #

def test_parse_canonical_seven_day_blocks():
    draft = schedule_parser.parse_schedule(_CANONICAL)
    assert draft is not None
    assert draft.repeat_days == 7
    got = [(b.title, b.start_time, b.duration_min) for b in draft.blocks]
    assert got == [
        ("Jogging", "06:00", 45),
        ("Sarapan", "07:00", 30),
        ("Baca Buku", "07:45", 45),
        ("Gym", "13:00", 90),
        ("Belajar", "15:00", 120),
        ("Ngoding", "20:00", 120),
    ]


def test_kerja_malam_ngoding_collapses_to_single_ngoding():
    titles = [b.title for b in schedule_parser.parse_schedule(_CANONICAL).blocks]
    assert "Ngoding" in titles and "Kerja" not in titles


def test_no_block_is_all_day_or_over_four_hours():
    for b in schedule_parser.parse_schedule(_CANONICAL).blocks:
        assert 0 < b.duration_min <= 240
        h, m = map(int, b.start_time.split(":"))
        assert (h * 60 + m) + b.duration_min <= 23 * 60 + 59  # never 23:59/all-day


def test_blocks_preserve_order_and_do_not_overlap():
    blocks = schedule_parser.parse_schedule(_CANONICAL).blocks

    def start(b):
        h, m = map(int, b.start_time.split(":"))
        return h * 60 + m

    for a, b in zip(blocks, blocks[1:]):
        assert start(b) >= start(a) + a.duration_min


@pytest.mark.parametrize("msg,expected", [
    ("atur jadwal 3 hari ke depan gym belajar", 3),
    ("buat jadwal seminggu jogging sarapan", 7),
    ("susun jadwal jogging", 7),                 # default count
    ("jadwalkan 20 hari gym", 14),               # clamped to max
])
def test_day_count_extraction(msg, expected):
    draft = schedule_parser.parse_schedule(msg)
    assert draft is not None and draft.repeat_days == expected


@pytest.mark.parametrize("msg", [
    "halo apa kabar",
    "catat pengeluaran makan 50 ribu",
    "kapan jadwal meeting besok?",   # no action verb -> not a schedule
    "buat jadwal",                   # verb but no known activity -> None (LLM handles)
])
def test_non_schedule_returns_none(msg):
    assert schedule_parser.parse_schedule(msg) is None


def test_schedule_request_is_skipped_for_memory():
    # Routine requests must not become memories (spec absolute rule).
    assert _should_skip_memory(_CANONICAL) is True


# --------------------- chat routing + approval ----------------------------- #

def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def test_schedule_chat_creates_one_routine_proposal(auth_client, db_session):
    resp = auth_client.post(f"{API}/ai/chat", json={"message": _CANONICAL})
    assert resp.status_code == 200, resp.text
    content = resp.json()["data"]["reply"]["content"].lower()
    assert "jadwal" in content and "7 hari" in content

    principal = _principal(auth_client)
    props = db_session.query(AiToolProposal).filter(
        AiToolProposal.workspace_id == principal.workspace_id,
        AiToolProposal.status == "PENDING",
    ).all()
    sched = [p for p in props if p.tool_name == "create_routine_schedule"]
    assert len(sched) == 1                       # ONE proposal, not N create_event
    assert sched[0].tool_payload["repeat_days"] == 7
    assert len(sched[0].tool_payload["blocks"]) == 6
    assert not any(p.tool_name == "create_event" for p in props)


def test_schedule_chat_does_not_create_memory(auth_client, db_session):
    auth_client.post(f"{API}/ai/chat", json={"message": _CANONICAL})
    principal = _principal(auth_client)
    mem = db_session.query(AiMemory).filter(
        AiMemory.workspace_id == principal.workspace_id).count()
    sug = db_session.query(AiMemorySuggestion).filter(
        AiMemorySuggestion.workspace_id == principal.workspace_id).count()
    assert mem == 0 and sug == 0


def test_approving_schedule_creates_timed_blocks_not_giant_event(auth_client, db_session):
    principal = _principal(auth_client)
    auth_client.post(f"{API}/ai/chat", json={"message": _CANONICAL})
    proposal = db_session.query(AiToolProposal).filter(
        AiToolProposal.workspace_id == principal.workspace_id,
        AiToolProposal.tool_name == "create_routine_schedule",
        AiToolProposal.status == "PENDING",
    ).one()

    approve_proposal(db_session, principal, proposal.id)

    events = db_session.query(CalendarEvent).filter(
        CalendarEvent.workspace_id == principal.workspace_id,
        CalendarEvent.is_deleted.is_(False),
    ).all()
    assert len(events) == 7 * 6                   # 7 days x 6 blocks
    for e in events:
        assert e.all_day is False
        assert e.start_at is not None and e.end_at is not None
        span_min = (e.end_at - e.start_at).total_seconds() / 60
        assert 0 < span_min <= 240                # never the 07:00-23:59 giant block
