"""Tests for multi-agent AI chat (up to 3 agents, concurrent, isolated failures)."""

import json

from tests.conftest import API


def test_rejects_more_than_seven_agents(auth_client):
    resp = auth_client.post(
        f"{API}/ai/chat/multi",
        json={"message": "hi", "provider_ids": ["openai", "anthropic", "gemini", "grok", "blackbox", "openrouter_1", "openrouter_2", "openrouter_3"]},
    )
    assert resp.status_code == 422, resp.text


def test_multi_run_persists_and_is_retrievable(auth_client):
    # Ollama (local, not configured here) + an external (blocked) agent: the run
    # and both per-agent rows must still persist honestly.
    resp = auth_client.post(
        f"{API}/ai/chat/multi",
        json={"message": "hello agents", "provider_ids": ["ollama", "openai"]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data["agent_responses"]) == 2
    run_id = data["run_id"]

    fetched = auth_client.get(f"{API}/ai/runs/{run_id}").json()["data"]
    assert fetched["run_id"] == run_id
    assert {r["provider_id"] for r in fetched["agent_responses"]} == {"ollama", "openai"}


def test_one_agent_failure_does_not_fail_all(auth_client, monkeypatch):
    # Allow external; mock the shared chat request so OpenAI succeeds. Ollama is
    # unconfigured -> not_configured. The run is "partial", not a total failure.
    auth_client.put(f"{API}/ai/policy", json={"allow_external": True})
    auth_client.put(
        f"{API}/ai/providers/openai",
        json={"secrets": {"api_key": "sk-real-looking-123"}, "enabled": True},
    )
    import app.services.ai_providers.base as base

    monkeypatch.setattr(
        base, "safe_request",
        lambda *a, **k: (200, {"choices": [{"message": {"content": "hi from gpt"}}]}, ""),
    )
    resp = auth_client.post(
        f"{API}/ai/chat/multi",
        json={"message": "hi", "provider_ids": ["openai", "ollama"]},
    )
    data = resp.json()["data"]
    by_id = {r["provider_id"]: r for r in data["agent_responses"]}
    assert by_id["openai"]["status"] == "completed"
    assert by_id["openai"]["content"] == "hi from gpt"
    assert by_id["ollama"]["status"] == "not_configured"
    assert data["status"] == "partial"


def test_multi_blocks_external_by_default(auth_client):
    auth_client.put(
        f"{API}/ai/providers/openai",
        json={"secrets": {"api_key": "sk-real-looking-123"}, "enabled": True},
    )
    resp = auth_client.post(
        f"{API}/ai/chat/multi", json={"message": "hi", "provider_ids": ["openai"]}
    )
    data = resp.json()["data"]
    assert data["agent_responses"][0]["status"] == "blocked"


def test_multi_never_returns_raw_secret(auth_client, monkeypatch):
    auth_client.put(f"{API}/ai/policy", json={"allow_external": True})
    secret = "sk-super-secret-zzz-999"
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
        f"{API}/ai/chat/multi", json={"message": "hi", "provider_ids": ["openai"]}
    )
    assert secret not in json.dumps(resp.json())
