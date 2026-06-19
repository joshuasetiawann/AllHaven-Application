"""Tests for the live n8n workflow integration (honest statuses, no key leak)."""

from tests.conftest import API

import app.services.n8n_service as n8n


def _config(monkeypatch, base="https://n8n.example", key="n8n-key"):
    monkeypatch.setattr(n8n.ics, "effective_config", lambda db, p, pid: ({"base_url": base} if base else {}, {"api_key": key} if key else {}))


def test_workflows_not_configured(auth_client, monkeypatch):
    _config(monkeypatch, base="", key="")
    data = auth_client.get(f"{API}/n8n/workflows").json()["data"]
    assert data["status"] == "not_configured" and data["workflows"] == []


def test_workflows_no_api_key(auth_client, monkeypatch):
    _config(monkeypatch, base="https://n8n.example", key="")
    data = auth_client.get(f"{API}/n8n/workflows").json()["data"]
    assert data["status"] == "no_api_key"


def test_workflows_online_parses_list(auth_client, monkeypatch):
    _config(monkeypatch)
    captured = {}

    def fake(method, url, **kw):
        captured["url"] = url
        captured["headers"] = kw.get("headers")
        return (200, {"data": [
            {"id": 1, "name": "Daily digest", "active": True, "updatedAt": "2026-06-10T00:00:00Z"},
            {"id": "abc", "name": "Sync", "active": False},
        ]}, "")

    monkeypatch.setattr(n8n, "safe_request", fake)
    data = auth_client.get(f"{API}/n8n/workflows").json()["data"]
    assert data["status"] == "online"
    assert [w["id"] for w in data["workflows"]] == ["1", "abc"]
    assert data["workflows"][0]["active"] is True
    # The API key is sent server-side and never returned.
    assert captured["headers"]["X-N8N-API-KEY"] == "n8n-key"
    assert "n8n-key" not in str(data)
    assert captured["url"].endswith("/api/v1/workflows")


def test_workflows_unauthorized(auth_client, monkeypatch):
    _config(monkeypatch)
    monkeypatch.setattr(n8n, "safe_request", lambda *a, **k: (401, {}, ""))
    data = auth_client.get(f"{API}/n8n/workflows").json()["data"]
    assert data["status"] == "unauthorized"


def test_workflows_unavailable(auth_client, monkeypatch):
    _config(monkeypatch)
    monkeypatch.setattr(n8n, "safe_request", lambda *a, **k: (None, None, "connection refused"))
    data = auth_client.get(f"{API}/n8n/workflows").json()["data"]
    assert data["status"] == "unavailable"


def test_set_active_toggles(auth_client, monkeypatch):
    _config(monkeypatch)
    captured = {}

    def fake(method, url, **kw):
        captured["url"] = url
        return (200, {"id": 1, "name": "Daily digest", "active": False}, "")

    monkeypatch.setattr(n8n, "safe_request", fake)
    resp = auth_client.post(f"{API}/n8n/workflows/1/active", json={"active": False})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["active"] is False
    assert captured["url"].endswith("/api/v1/workflows/1/deactivate")


def test_set_active_requires_config(auth_client, monkeypatch):
    _config(monkeypatch, base="", key="")
    resp = auth_client.post(f"{API}/n8n/workflows/1/active", json={"active": True})
    assert resp.status_code == 422, resp.text
