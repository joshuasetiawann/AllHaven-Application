"""API docs exposure policy."""

from fastapi.testclient import TestClient

from app.core.config import Settings
import app.main as main_module


def test_api_docs_enabled_in_local_mode(client):
    assert client.get("/docs").status_code == 200
    root = client.get("/").json()["data"]
    assert root["docs"] == "/docs"


def test_api_docs_disabled_in_production_by_default(monkeypatch):
    prod_settings = Settings(
        APP_ENV="production",
        SECRET_KEY="x" * 48,
        DATABASE_URL="sqlite+pysqlite:///:memory:",
    )
    monkeypatch.setattr(main_module, "settings", prod_settings)

    prod_app = main_module.create_app()
    with TestClient(prod_app) as prod_client:
        assert prod_client.get("/docs").status_code == 404
        assert prod_client.get("/redoc").status_code == 404
        assert prod_client.get("/openapi.json").status_code == 404
        assert "docs" not in prod_client.get("/").json()["data"]


def test_api_docs_can_be_explicitly_enabled_in_production(monkeypatch):
    prod_settings = Settings(
        APP_ENV="production",
        SECRET_KEY="x" * 48,
        API_DOCS_ENABLED=True,
        DATABASE_URL="sqlite+pysqlite:///:memory:",
    )
    monkeypatch.setattr(main_module, "settings", prod_settings)

    prod_app = main_module.create_app()
    with TestClient(prod_app) as prod_client:
        assert prod_client.get("/docs").status_code == 200
        assert prod_client.get("/openapi.json").status_code == 200
