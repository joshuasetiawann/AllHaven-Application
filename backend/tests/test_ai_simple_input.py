"""4.0 gap fixes: simple-input short-circuit (P2), quality gate (P3), ROUTINE
intent (P4), bare "dapat <amount>" income (P6), and the finance/schedule/smalltalk
short-circuit on the debate and reasoning paths (P6).

Providers are stubbed via ``plan_chat`` (same pattern as test_ai_debate.py).
"""

import pytest

from tests.conftest import API

import app.services.ai_provider_router as router_mod
from app.services import ai_intent_router as router
from app.services.ai_provider_router import ChatPlan
from app.services.ai_providers.base import ChatResult
from app.services.memory_extraction_service import _should_skip_memory
from app.services.reasoning import quality


# ------------------------------ intent router ------------------------------ #

@pytest.mark.parametrize("msg", [
    "halo", "Halo!", "hai", "hi", "makasih ya", "terima kasih banyak",
    "ok sip", "oke", "selamat pagi", "p", "apa kabar?", "halo apa kabar",
    "thank you so much", "test", "noted",
])
def test_simple_messages_detected(msg):
    assert router.is_simple_message(msg) is True


@pytest.mark.parametrize("msg", [
    "halo, tolong hapus semua task",
    "oke lanjutkan",
    "berapa pengeluaran bulan ini?",
    "buatkan task belajar",
    "coba jalankan backup sekarang",
    "",
])
def test_non_simple_messages_pass_through(msg):
    assert router.is_simple_message(msg) is False


def test_bare_dapat_with_amount_is_income():
    res = router.classify("dapat 5000000")
    assert res.intent == router.FINANCE
    assert res.txn_type == "INCOME"
    assert res.amount == 5_000_000


def test_dapet_variant_with_qualified_amount_is_income():
    res = router.classify("barusan dapet 500 ribu dari client")
    assert res.intent == router.FINANCE and res.txn_type == "INCOME"
    assert res.amount == 500_000


def test_dapat_without_amount_is_not_finance():
    assert router.classify("dapat 3 buku baru").intent == router.GENERAL
    assert router.classify("saya dapat kabar baik").intent == router.GENERAL


def test_routine_phrases_get_routine_intent():
    assert router.classify("setiap pagi saya jogging jam 6").intent == router.ROUTINE
    assert router.classify("tolong buat rutinitas belajar").intent == router.ROUTINE
    assert router.classify("jadwal mingguan olahraga dong").intent == router.ROUTINE


def test_explicit_remember_beats_routine():
    assert router.classify("ingat bahwa setiap senin saya meeting").intent == router.MEMORY


def test_routine_messages_skip_memory_gate():
    assert _should_skip_memory("setiap pagi saya jogging jam 6") is True
    assert _should_skip_memory("tolong buat rutinitas belajar malam") is True


# ------------------------------ quality no-op ------------------------------ #

@pytest.mark.parametrize("reply,expected", [
    ("completed", True), ("Completed.", True), ("done", True), ("selesai!", True),
    ("Task completed", True), ("ok", True),
    ("Saya sudah membuat draft pengeluaran Rp50.000.", False), ("", False),
])
def test_is_noop_reply(reply, expected):
    assert quality.is_noop_reply(reply) is expected


# ------------------------- orchestrated chat paths ------------------------- #

def _plan(pid: str, name: str, *, content: str = None, tool_loop: bool = False,
          captured: dict = None) -> ChatPlan:
    def _runner(messages, params=None, tools=None):
        if captured is not None:
            captured.setdefault("calls", []).append({"messages": messages, "tools": tools})
        prompt = messages[-1]["content"] if messages else ""
        return ChatResult(True, content=content if content is not None else f"[{name}] {prompt}")

    return ChatPlan(pid, name, False, True, True, "queued", "", _runner,
                    supports_tool_loop=tool_loop)


def _patch_plans(monkeypatch, plans: dict[str, ChatPlan]) -> None:
    monkeypatch.setattr(
        router_mod, "plan_chat",
        lambda db, principal, pid=None: plans[pid or next(iter(plans))],
    )


def test_greeting_skips_tool_loop_on_tool_capable_provider(auth_client, monkeypatch):
    captured: dict = {}
    _patch_plans(monkeypatch, {
        "openai": _plan("openai", "GPT Agent", content="Halo! Ada yang bisa kubantu?",
                        tool_loop=True, captured=captured),
    })
    resp = auth_client.post(f"{API}/ai/chat", json={"message": "halo", "provider_id": "openai"})
    assert resp.status_code == 200, resp.text
    assert "Halo" in resp.json()["data"]["reply"]["content"]
    # The provider was called WITHOUT tool definitions — plain chat, no tool loop.
    assert captured["calls"], "provider was not called"
    assert all(c["tools"] is None for c in captured["calls"])


def test_greeting_multi_agent_answers_once(auth_client, monkeypatch):
    captured: dict = {}
    _patch_plans(monkeypatch, {
        "openai": _plan("openai", "GPT Agent", content="Halo juga!", captured=captured),
        "grok": _plan("grok", "Grok", captured=captured),
    })
    resp = auth_client.post(
        f"{API}/ai/chat/multi",
        json={"message": "halo", "provider_ids": ["openai", "grok"]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    done = [r for r in data["agent_responses"] if r["status"] == "completed"]
    # Exactly ONE warm reply — no fan-out of the greeting to every agent.
    assert len(done) == 1
    assert len(captured["calls"]) == 1


def test_finance_message_in_debate_becomes_single_proposal(auth_client, monkeypatch):
    captured: dict = {}
    _patch_plans(monkeypatch, {
        "openai": _plan("openai", "GPT Agent", captured=captured),
        "grok": _plan("grok", "Grok", captured=captured),
    })
    resp = auth_client.post(
        f"{API}/ai/chat/debate",
        json={"message": "catat pengeluaran makan 50 ribu",
              "provider_ids": ["openai", "grok"], "rounds": 2},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "completed"
    # No debate rounds ran — the deterministic finance proposal IS the answer.
    assert captured.get("calls") is None
    finals = [r for r in data["agent_responses"] if r["meta"].get("phase") == "synthesis"]
    assert len(finals) == 1 and len(data["agent_responses"]) == 1
    assert "draft pengeluaran" in (finals[0]["content"] or "")

    proposals = auth_client.get(f"{API}/ai/proposals").json()["data"]
    assert any(p["tool_name"] == "create_transaction" for p in proposals)


def test_greeting_in_debate_gets_one_warm_reply(auth_client, monkeypatch):
    captured: dict = {}
    _patch_plans(monkeypatch, {
        "openai": _plan("openai", "GPT Agent", content="Halo! Semua sistem siap.",
                        captured=captured),
        "grok": _plan("grok", "Grok", captured=captured),
    })
    resp = auth_client.post(
        f"{API}/ai/chat/debate",
        json={"message": "halo", "provider_ids": ["openai", "grok"], "rounds": 2},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "completed"
    assert len(data["agent_responses"]) == 1
    assert len(captured["calls"]) == 1  # one plain call, no rounds/synthesis


def test_finance_message_in_reasoning_becomes_single_proposal(auth_client, monkeypatch):
    captured: dict = {}
    _patch_plans(monkeypatch, {
        "openai": _plan("openai", "GPT Agent", captured=captured),
    })
    resp = auth_client.post(
        f"{API}/ai/chat/reason",
        json={"message": "saya dapat 5000000 dari project",
              "provider_ids": ["openai"]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "completed"
    assert captured.get("calls") is None  # deterministic — no model call
    finals = [r for r in data["agent_responses"] if r["meta"].get("reasoning_final")]
    assert len(finals) == 1
    assert "draft pendapatan" in (finals[0]["content"] or "")


def test_noop_reply_after_tools_replaced_with_summary(auth_client, monkeypatch):
    """A tool-capable model that answers a bare 'completed' after running tools
    gets its reply replaced by the specific fallback summary."""
    state = {"round": 0}

    def _runner(messages, params=None, tools=None):
        state["round"] += 1
        if state["round"] == 1 and tools:
            import json as _json
            return ChatResult(True, content="", tool_calls=[
                {"id": "c1", "name": "create_task",
                 "arguments": _json.dumps({"title": "Belajar"})},
            ])
        return ChatResult(True, content="completed")

    plan = ChatPlan("openai", "GPT Agent", False, True, True, "queued", "", _runner,
                    supports_tool_loop=True)
    _patch_plans(monkeypatch, {"openai": plan})
    resp = auth_client.post(
        f"{API}/ai/chat",
        json={"message": "tolong siapkan rencana belajar untuk saya", "provider_id": "openai"},
    )
    assert resp.status_code == 200, resp.text
    content = resp.json()["data"]["reply"]["content"]
    assert content.strip().lower() != "completed"
    assert "persetujuan" in content or "Selesai menjalankan" in content
