"""Integration tests for the reasoning council (Analyst/Critic/Synthesizer).

Providers are stubbed via ``plan_chat`` so we exercise the orchestration: role
assignment, rejecting irrelevant critique, the low-quality retry, fast/deep
depth, and that raw secrets are never returned.
"""

import json

from tests.conftest import API

import app.services.ai_provider_router as router_mod
from app.services.ai_provider_router import ChatPlan
from app.services.ai_providers.base import ChatResult


def _plan(pid, name, *, contents=None, content="A grounded, on-topic answer.", ok=True, external=True):
    seq = list(contents) if contents else None

    def _runner(messages, params=None):
        if not ok:
            return ChatResult(False, error="provider boom")
        if seq is not None:
            chosen = seq.pop(0) if len(seq) > 1 else seq[0]
            return ChatResult(True, content=chosen)
        return ChatResult(True, content=content)

    return ChatPlan(pid, name, external, True, True, "queued", "", _runner)


def _patch(monkeypatch, plans):
    monkeypatch.setattr(router_mod, "plan_chat", lambda db, principal, pid: plans[pid])


def test_reason_rejects_more_than_ten_agents(auth_client):
    resp = auth_client.post(
        f"{API}/ai/chat/reason",
        json={
            "message": "hi",
            "provider_ids": [
                "openai", "anthropic", "gemini", "grok", "blackbox", "cursor",
                "deepseek", "qwen", "openrouter_1", "openrouter_2", "openrouter_3",
            ],
        },
    )
    assert resp.status_code == 422, resp.text


def test_reason_deep_runs_three_roles(auth_client, monkeypatch):
    _patch(monkeypatch, {
        "openai": _plan("openai", "Analyst GPT", content="Revenue 10,000,000 at 15% margin => EBITDA 1,500,000."),
        "grok": _plan("grok", "Critic Grok", content="The margin assumption looks right; consider downside risk."),
        "gemini": _plan("gemini", "Synth Gemini", content="EBITDA is 1,500,000 (15% of 10,000,000); recommend monitoring costs."),
    })
    resp = auth_client.post(
        f"{API}/ai/chat/reason",
        json={"message": "Revenue is 10,000,000 with 15% EBITDA margin. What is EBITDA?",
              "provider_ids": ["openai", "grok", "gemini"], "thinking_mode": "deep"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    phases = {r["meta"]["phase"] for r in data["agent_responses"]}
    assert {"analyst", "critic", "synthesis"} <= phases

    session_id = data["session_id"]
    msgs = auth_client.get(f"{API}/ai/sessions/{session_id}/messages").json()["data"]
    finals = [m for m in msgs if (m.get("meta") or {}).get("reasoning_final")]
    assert len(finals) == 1
    assert finals[0]["meta"]["mode"] == "deep"
    assert "quality" in finals[0]["meta"] and "reasoning_summary" in finals[0]["meta"]


def test_reason_rejects_irrelevant_porter_critique(auth_client, monkeypatch):
    _patch(monkeypatch, {
        "openai": _plan("openai", "Analyst", content="Porter: rivalry, new entrants, buyers, suppliers, substitutes."),
        "grok": _plan("grok", "Critic", content="Your Porter five forces analysis forgot pengadilan as a force."),
        "gemini": _plan("gemini", "Synth", content="Porter's five forces are rivalry, new entrants, buyers, suppliers, substitutes."),
    })
    resp = auth_client.post(
        f"{API}/ai/chat/reason",
        json={"message": "Give a Porter's Five Forces analysis of our market.",
              "provider_ids": ["openai", "grok", "gemini"], "thinking_mode": "deep"},
    )
    data = resp.json()["data"]
    critic = next(r for r in data["agent_responses"] if r["meta"]["phase"] == "critic")
    assert critic["meta"]["critique_relevant"] is False
    final = next(r for r in data["agent_responses"] if r["meta"]["phase"] == "synthesis")
    assert final["meta"]["rejected_critique"] is True


def test_reason_low_quality_triggers_retry(auth_client, monkeypatch):
    # One agent, balanced: analyst -> synth(bad, invalid Porter) -> retry synth(good).
    _patch(monkeypatch, {
        "openai": _plan("openai", "GPT", contents=[
            "Porter five forces analysis of the market.",                          # analyst
            "Porter five forces include pengadilan as the dominant force.",        # synth (low quality)
            "Porter's five forces: rivalry, new entrants, buyers, suppliers, substitutes.",  # retry (good)
        ]),
    })
    resp = auth_client.post(
        f"{API}/ai/chat/reason",
        json={"message": "Give a Porter's Five Forces analysis.", "provider_ids": ["openai"], "thinking_mode": "balance"},
    )
    data = resp.json()["data"]
    final = next(r for r in data["agent_responses"] if r["meta"]["phase"] == "synthesis")
    assert final["meta"]["retried"] is True
    assert "pengadilan" not in (final["content"] or "")


def test_reason_fast_is_single_pass(auth_client, monkeypatch):
    _patch(monkeypatch, {"openai": _plan("openai", "GPT", content="Direct grounded answer.")})
    resp = auth_client.post(
        f"{API}/ai/chat/reason",
        json={"message": "Summarize the key risks.", "provider_ids": ["openai"], "thinking_mode": "fast"},
    )
    data = resp.json()["data"]
    phases = [r["meta"]["phase"] for r in data["agent_responses"]]
    assert "critic" not in phases
    final = next(r for r in data["agent_responses"] if r["meta"]["phase"] == "synthesis")
    assert final["meta"]["mode"] == "fast" and final["meta"]["retried"] is False


def test_reason_never_returns_raw_secret(auth_client, monkeypatch):
    auth_client.put(f"{API}/ai/policy", json={"allow_external": True})
    secret = "sk-super-secret-reason-555"
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
        f"{API}/ai/chat/reason",
        json={"message": "What is EBITDA?", "provider_ids": ["openai"], "thinking_mode": "balance"},
    )
    assert resp.status_code == 200, resp.text
    assert secret not in json.dumps(resp.json())
