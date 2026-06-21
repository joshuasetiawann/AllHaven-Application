"""Current date/time awareness: the AI is always told today's date (so it never
invents a stale 2023 date), time_payload exposes year/month/day, and a create_event
with no date anchors to today."""
import uuid
from datetime import date

from app.core.principal import Principal
from app.services import ai_orchestrator
from app.services.ai_local_answers import time_payload
from tests.conftest import API


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def test_time_payload_exposes_year_month_day():
    t = time_payload()
    today = date.fromisoformat(t["date"])
    assert t["year"] == today.year
    assert t["month"] == today.month
    assert t["day"] == today.day


def test_current_context_block_has_today_and_no_invent_rule():
    block = ai_orchestrator._current_context_block()
    assert "Current context" in block
    assert time_payload()["date"] in block          # today's real date is in the prompt
    assert "never invent" in block.lower()


def test_create_event_defaults_missing_start_to_today(auth_client, db_session):
    from app.services.ai_tools_registry import _h_create_event
    principal = _principal(auth_client)
    res = _h_create_event(db_session, principal, {"title": "Rapat tanpa tanggal"})
    start = str(res["event"]["start_at"])
    assert time_payload()["date"] in start          # today, never a 2023 fallback


def test_finance_summary_tool_no_keyerror(auth_client, db_session):
    # _h_finance_summary reads today["year"]/["month"] — used to KeyError before the fix.
    from app.services.ai_tools_registry import _h_finance_summary
    principal = _principal(auth_client)
    res = _h_finance_summary(db_session, principal, {})
    assert isinstance(res, dict)
