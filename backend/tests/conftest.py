"""Pytest fixtures.

The suite runs against an in-memory SQLite database (configured BEFORE importing
the app) so it is fast and needs no external services. Production always uses
PostgreSQL via DATABASE_URL.
"""

from __future__ import annotations

import os
import tempfile

# Configure the environment before any app import so settings pick it up.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["SETTINGS_ENCRYPTION_KEY"] = "test-encryption-key"
os.environ["BACKEND_CORS_ORIGINS"] = "http://localhost:3000"
os.environ["AI_ALLOW_EXTERNAL_PROVIDERS"] = "false"
os.environ["AI_DEFAULT_PROVIDER"] = "ollama"
# Redirect the .env mirror and Drive storage to temp dirs so tests never touch
# the real repo .env or pollute the working tree.
_TMP = tempfile.mkdtemp(prefix="allhaven-test-")
os.environ["ENV_SYNC_PATH"] = os.path.join(_TMP, ".env")
os.environ["DRIVE_STORAGE_DIR"] = os.path.join(_TMP, "drive")
# Force these empty so a local .env file can never make tests non-deterministic
# (real env vars take priority over any .env file).
for _placeholder in (
    "OLLAMA_BASE_URL",
    "OLLAMA_DEFAULT_MODEL",
    "N8N_BASE_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "GOOGLE_CALENDAR_CLIENT_ID",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "WEATHER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GROK_API_KEY",
    "BLACKBOX_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENROUTER_1_API_KEY",
    "OPENROUTER_1_DEFAULT_MODEL",
    "OPENROUTER_2_API_KEY",
    "OPENROUTER_2_DEFAULT_MODEL",
    "OPENROUTER_3_API_KEY",
    "OPENROUTER_3_DEFAULT_MODEL",
    "N8N_API_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "GOOGLE_CALENDAR_CLIENT_SECRET",
    "WEATHER_PROVIDER",
):
    os.environ[_placeholder] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.domain.base import Base  # noqa: E402
from app.main import app  # noqa: E402

API = "/api/v1"


@pytest.fixture(autouse=True)
def _reset_database():
    """Fresh schema for every test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def auth_client(client):
    """A client with a registered user's bearer token attached."""
    resp = client.post(
        f"{API}/auth/register",
        json={
            "email": "owner@example.com",
            "password": "password123",
            "full_name": "Owner User",
        },
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
