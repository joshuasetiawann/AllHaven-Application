"""CORS policy regressions."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def _preflight(client, origin: str):
    return client.options(
        "/api/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )


def test_local_cors_allows_private_lan_tailscale_and_capacitor_origins(client):
    for origin in (
        "http://localhost:3000",
        "https://localhost",
        "capacitor://localhost",
        "http://192.168.1.7:3000",
        "http://100.91.122.124:3000",
        "https://joo.tail01a7d3.ts.net",
    ):
        resp = _preflight(client, origin)

        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == origin
        assert resp.headers["access-control-allow-credentials"] == "true"


def test_local_cors_rejects_public_origins(client):
    resp = _preflight(client, "https://evil.example")

    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers


def test_production_local_cors_allows_both_loopback_aliases_on_frontend_port(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "BACKEND_CORS_ALLOW_ALL", False)
    monkeypatch.setattr(
        settings,
        "BACKEND_CORS_ORIGINS",
        "http://localhost:3210,http://127.0.0.1:3210,https://localhost,capacitor://localhost",
    )

    with TestClient(create_app()) as production_client:
        for origin in ("http://localhost:3210", "http://127.0.0.1:3210"):
            resp = _preflight(production_client, origin)
            assert resp.status_code == 200
            assert resp.headers["access-control-allow-origin"] == origin

        for rejected in ("http://127.0.0.1:3211", "https://evil.example"):
            resp = _preflight(production_client, rejected)
            assert resp.status_code == 400
            assert "access-control-allow-origin" not in resp.headers
