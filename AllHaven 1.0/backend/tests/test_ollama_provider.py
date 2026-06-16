"""Ollama local provider verification tests (honest status, no fake online)."""

from tests.conftest import API


def test_ollama_missing_base_url_is_not_configured(auth_client):
    resp = auth_client.post(f"{API}/ai/providers/ollama/test")
    # No base_url saved or in env → not configured (never online).
    assert resp.json()["data"]["status"] in ("not_configured",)


def test_ollama_unreachable_is_unavailable(auth_client):
    auth_client.put(
        f"{API}/ai/providers/ollama",
        json={"public_config": {"base_url": "http://127.0.0.1:1"}, "default_model": "llama3.1"},
    )
    resp = auth_client.post(f"{API}/ai/providers/ollama/test")
    status = resp.json()["data"]["status"]
    assert status in ("unavailable", "error")
    assert status != "online"


def test_ollama_online_when_tags_succeed(auth_client, monkeypatch):
    import app.services.ai_providers.ollama_provider as op

    # Simulate a running Ollama: GET /api/tags returns 200.
    monkeypatch.setattr(op, "safe_request", lambda *a, **k: (200, {"models": []}, ""))
    auth_client.put(
        f"{API}/ai/providers/ollama",
        json={"public_config": {"base_url": "http://localhost:11434"}, "default_model": "llama3.1"},
    )
    resp = auth_client.post(f"{API}/ai/providers/ollama/test")
    assert resp.json()["data"]["status"] == "online"


def test_ollama_needs_no_api_key(auth_client):
    data = auth_client.get(f"{API}/ai/providers").json()["data"]["providers"]
    ollama = next(p for p in data if p["id"] == "ollama")
    assert ollama["api_key_required"] is False
    assert ollama["external"] is False
