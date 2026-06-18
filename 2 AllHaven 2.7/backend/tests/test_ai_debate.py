"""Tests for multi-agent debate (agents argue across rounds, then synthesize).

The orchestration is decoupled from real providers by monkeypatching
``ai_provider_router.plan_chat`` to return canned, runnable plans — so these tests
exercise the debate logic (rounds, isolation, synthesis, persistence) without any
network calls or provider response-format coupling.
"""

import json

from tests.conftest import API

import app.services.ai_provider_router as router_mod
from app.services.ai_provider_router import ChatPlan
from app.services.ai_providers.base import ChatResult


def _plan(pid: str, name: str, *, ok: bool = True, external: bool = False) -> ChatPlan:
    def _runner(messages, params=None):
        # Echo a tag + the prompt so we can assert the debate actually fed each
        # agent the question / the other agents' answers.
        prompt = messages[-1]["content"] if messages else ""
        if ok:
            return ChatResult(True, content=f"[{name}] {prompt}")
        return ChatResult(False, error="provider boom")

    return ChatPlan(pid, name, external, True, True, "queued", "", _runner)


def _patch_plans(monkeypatch, plans: dict[str, ChatPlan]) -> None:
    monkeypatch.setattr(router_mod, "plan_chat", lambda db, principal, pid: plans[pid])


def test_debate_rejects_more_than_seven_agents(auth_client):
    resp = auth_client.post(
        f"{API}/ai/chat/debate",
        json={"message": "hi", "provider_ids": ["openai", "anthropic", "gemini", "grok", "blackbox", "openrouter_1", "openrouter_2", "openrouter_3"]},
    )
    assert resp.status_code == 422, resp.text


def test_debate_two_agents_run_rounds_and_synthesize(auth_client, monkeypatch):
    _patch_plans(monkeypatch, {
        "openai": _plan("openai", "GPT Agent", external=True),
        "grok": _plan("grok", "Grok", external=True),
    })
    resp = auth_client.post(
        f"{API}/ai/chat/debate",
        json={"message": "What is 2+2?", "provider_ids": ["openai", "grok"], "rounds": 2},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "completed"
    run_id = data["run_id"]
    session_id = data["session_id"]

    # 2 agents x 2 rounds (opening + rebuttal) + 1 synthesis row.
    assert len(data["agent_responses"]) == 5
    phases = [r["meta"]["phase"] for r in data["agent_responses"]]
    assert phases.count("opening") == 2
    assert phases.count("rebuttal") == 2
    assert phases.count("synthesis") == 1

    # The conversation thread persists the debate: user + 4 round turns + final.
    msgs = auth_client.get(f"{API}/ai/sessions/{session_id}/messages").json()["data"]
    assert msgs[0]["role"] == "user"
    finals = [m for m in msgs if (m.get("meta") or {}).get("debate_final")]
    assert len(finals) == 1 and finals[0]["meta"]["status"] == "completed"

    # The rebuttal prompt must have included the *other* agent's answer.
    rebuttals = [m for m in msgs if (m.get("meta") or {}).get("phase") == "rebuttal"]
    assert rebuttals and any("answered" in m["content"] for m in rebuttals)

    # get_run returns the same run with the synthesis included.
    fetched = auth_client.get(f"{API}/ai/runs/{run_id}").json()["data"]
    assert any(r["meta"]["phase"] == "synthesis" for r in fetched["agent_responses"])


def test_debate_one_agent_failure_is_isolated_and_partial(auth_client, monkeypatch):
    _patch_plans(monkeypatch, {
        "openai": _plan("openai", "GPT Agent", ok=True, external=True),
        "grok": _plan("grok", "Grok", ok=False, external=True),
    })
    resp = auth_client.post(
        f"{API}/ai/chat/debate",
        json={"message": "debate this", "provider_ids": ["openai", "grok"], "rounds": 2},
    )
    data = resp.json()["data"]
    # One agent failing must not fail the run: synthesis still succeeds -> partial.
    assert data["status"] == "partial"
    by_phase_status = {(r["provider_id"], r["meta"]["phase"]): r["status"] for r in data["agent_responses"]}
    assert by_phase_status[("grok", "opening")] == "error"
    assert by_phase_status[("openai", "opening")] == "completed"
    assert by_phase_status[("openai", "synthesis")] == "completed"


def test_debate_with_no_runnable_agents_is_honest_error(auth_client):
    # No monkeypatch: real plan_chat. Ollama is not configured (no base_url) and
    # OpenAI is external (blocked by default) -> nothing can run, nothing to debate.
    resp = auth_client.post(
        f"{API}/ai/chat/debate",
        json={"message": "hello", "provider_ids": ["ollama", "openai"]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "error"
    session_id = data["session_id"]
    msgs = auth_client.get(f"{API}/ai/sessions/{session_id}/messages").json()["data"]
    finals = [m for m in msgs if (m.get("meta") or {}).get("debate_final")]
    assert len(finals) == 1 and finals[0]["meta"]["status"] == "error"


def test_debate_single_runnable_agent_returns_its_answer(auth_client, monkeypatch):
    # Only one runnable agent: there is no debate, so its answer is the result
    # (no fabricated rounds, no synthesis call).
    _patch_plans(monkeypatch, {"openai": _plan("openai", "GPT Agent", external=True)})
    resp = auth_client.post(
        f"{API}/ai/chat/debate",
        json={"message": "solo", "provider_ids": ["openai"], "rounds": 3},
    )
    data = resp.json()["data"]
    assert data["status"] == "completed"
    phases = [r["meta"]["phase"] for r in data["agent_responses"]]
    assert phases.count("opening") == 1
    assert "rebuttal" not in phases  # one agent => no rebuttal rounds


def test_debate_never_returns_raw_secret(auth_client, monkeypatch):
    auth_client.put(f"{API}/ai/policy", json={"allow_external": True})
    secret = "sk-super-secret-debate-777"
    auth_client.put(
        f"{API}/ai/providers/openai",
        json={"secrets": {"api_key": secret}, "enabled": True},
    )
    import app.services.ai_providers.base as base

    monkeypatch.setattr(
        base, "safe_request",
        lambda *a, **k: (200, {"choices": [{"message": {"content": "ok"}}]}, ""),
    )
    resp = auth_client.post(
        f"{API}/ai/chat/debate", json={"message": "hi", "provider_ids": ["openai"]}
    )
    assert resp.status_code == 200, resp.text
    assert secret not in json.dumps(resp.json())
