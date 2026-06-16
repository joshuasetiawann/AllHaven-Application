"""Tests for the multi-provider AI system."""

import json

from tests.conftest import API


def test_provider_list_has_six_apis_plus_ollama(auth_client):
    data = auth_client.get(f"{API}/ai/providers").json()["data"]["providers"]
    ids = {p["id"] for p in data}
    assert {"openai", "anthropic", "gemini", "grok", "blackbox", "openrouter", "ollama"}.issubset(ids)
    assert len(data) == 7
    ollama = next(p for p in data if p["id"] == "ollama")
    assert ollama["external"] is False
    assert ollama["api_key_required"] is False
    # GPT Agent display name
    assert next(p for p in data if p["id"] == "openai")["name"] == "GPT Agent"


def test_ollama_configurable_without_api_key(auth_client):
    resp = auth_client.put(
        f"{API}/ai/providers/ollama",
        json={"public_config": {"base_url": "http://localhost:11434"}, "default_model": "llama3.1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "configured"


def test_saving_provider_key_never_returns_raw(auth_client):
    secret = "sk-openai-doodad-7777"
    resp = auth_client.put(
        f"{API}/ai/providers/openai",
        json={"secrets": {"api_key": secret}, "default_model": "gpt-4.1-mini", "enabled": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["secrets"]["api_key"]["configured"] is True
    assert secret not in json.dumps(body)
    assert body["data"]["status"] == "configured"


def test_external_provider_chat_blocked_when_disabled(auth_client):
    # External providers are disabled by default (AI_ALLOW_EXTERNAL_PROVIDERS unset).
    auth_client.put(
        f"{API}/ai/providers/openai",
        json={"secrets": {"api_key": "sk-test-123456"}, "enabled": True},
    )
    resp = auth_client.post(f"{API}/ai/chat", json={"message": "hello", "provider_id": "openai"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["blocked"] is True
    assert data["ai_configured"] is False
    assert "external" in data["reply"]["content"].lower()


def test_policy_toggle_unblocks_external_chat(auth_client, monkeypatch):
    # Default: external is blocked.
    auth_client.put(
        f"{API}/ai/providers/openai",
        json={"secrets": {"api_key": "sk-real-looking-123"}, "enabled": True},
    )
    blocked = auth_client.post(f"{API}/ai/chat", json={"message": "hi", "provider_id": "openai"})
    assert blocked.json()["data"]["blocked"] is True

    # Allow external via the workspace policy toggle.
    pol = auth_client.put(f"{API}/ai/policy", json={"allow_external": True})
    assert pol.json()["data"]["allow_external"] is True

    # Now it's no longer blocked (chat() lives in base; mock its request).
    import app.services.ai_providers.base as base

    monkeypatch.setattr(
        base, "safe_request", lambda *a, **k: (200, {"choices": [{"message": {"content": "hello!"}}]}, "")
    )
    allowed = auth_client.post(f"{API}/ai/chat", json={"message": "hi", "provider_id": "openai"})
    data = allowed.json()["data"]
    assert data["blocked"] is False
    assert data["ai_configured"] is True


def test_local_ollama_not_blocked_by_external_gate(auth_client):
    # Ollama is local: not blocked, but honestly reports not configured here.
    resp = auth_client.post(f"{API}/ai/chat", json={"message": "hi", "provider_id": "ollama"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["blocked"] is False
    assert data["ai_configured"] is False
    assert "not configured" in data["reply"]["content"].lower()


def test_provider_disable_sets_disabled(auth_client):
    auth_client.put(
        f"{API}/ai/providers/anthropic",
        json={"secrets": {"api_key": "sk-ant-abc123"}, "enabled": True},
    )
    resp = auth_client.post(f"{API}/ai/providers/anthropic/disable")
    assert resp.json()["data"]["status"] == "disabled"


def test_saving_random_key_is_configured_not_online(auth_client):
    # Saving must NEVER auto-verify to online — only Test Connection can do that.
    resp = auth_client.put(
        f"{API}/ai/providers/openai",
        json={"secrets": {"api_key": "sk-totally-random-abc"}, "enabled": True},
    )
    assert resp.json()["data"]["status"] == "configured"


def test_random_key_does_not_become_online_openrouter(auth_client, monkeypatch):
    # OpenRouter's /models is public; verification must use the authed /key endpoint.
    # Simulate an invalid key (HTTP 401) -> error, never online.
    import app.services.ai_providers.openrouter_provider as orp

    monkeypatch.setattr(orp, "safe_request", lambda *a, **k: (401, {"error": "no auth"}, ""))
    auth_client.put(
        f"{API}/ai/providers/openrouter",
        json={"secrets": {"api_key": "sk-or-random"}, "enabled": True},
    )
    resp = auth_client.post(f"{API}/ai/providers/openrouter/test")
    assert resp.json()["data"]["status"] == "error"


def test_openrouter_valid_key_online_when_mocked(auth_client, monkeypatch):
    import app.services.ai_providers.openrouter_provider as orp

    monkeypatch.setattr(orp, "safe_request", lambda *a, **k: (200, {"data": {}}, ""))
    auth_client.put(
        f"{API}/ai/providers/openrouter",
        json={"secrets": {"api_key": "sk-or-valid"}, "enabled": True},
    )
    resp = auth_client.post(f"{API}/ai/providers/openrouter/test")
    assert resp.json()["data"]["status"] == "online"


def test_blackbox_never_online_from_test(auth_client):
    # Verification endpoint is unclear → configured (not verified), never online.
    auth_client.put(
        f"{API}/ai/providers/blackbox",
        json={"secrets": {"api_key": "bb-anything"}, "enabled": True},
    )
    resp = auth_client.post(f"{API}/ai/providers/blackbox/test")
    assert resp.json()["data"]["status"] == "configured"
