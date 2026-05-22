"""Tests for the local .env mirror service and its wiring into Settings."""

import glob
import os

from tests.conftest import API

from app.core.config import settings
from app.services import env_file_service


def _read_env() -> str:
    path = settings.env_file_path
    return open(path, encoding="utf-8").read() if os.path.exists(path) else ""


def test_save_provider_returns_env_sync_and_writes_allowed_key(auth_client):
    secret = "sk-openrouter-live-abc123"
    resp = auth_client.put(
        f"{API}/ai/providers/openrouter_1",
        json={"secrets": {"api_key": secret}, "default_model": "openai/gpt-4.1-mini", "enabled": True},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "configured"
    assert data["env_sync"]["status"] == "success"
    assert "OPENROUTER_1_API_KEY" in data["env_sync"]["keys"]

    env = _read_env()
    assert "OPENROUTER_1_API_KEY=" in env
    assert "OPENROUTER_1_DEFAULT_MODEL=" in env


def test_env_sync_creates_backup_on_second_write(auth_client):
    auth_client.put(
        f"{API}/ai/providers/openai",
        json={"secrets": {"api_key": "sk-openai-aaa111"}, "enabled": True},
    )
    # Second write should back up the existing .env first.
    auth_client.put(
        f"{API}/ai/providers/openai",
        json={"secrets": {"api_key": "sk-openai-bbb222"}, "enabled": True},
    )
    backups = glob.glob(settings.env_file_path + ".bak.*")
    assert backups, "expected at least one .env.bak.<ts> backup"


def test_env_sync_rejects_arbitrary_keys():
    # Direct service call: keys outside the allowlist must never be written.
    result = env_file_service.sync_env({"EVIL_KEY": "x", "PATH": "/tmp", "SECRET_KEY": "leak"})
    assert result["status"] == "skipped"
    assert result["keys"] == []
    env = _read_env()
    assert "EVIL_KEY" not in env
    assert "PATH=/tmp" not in env


def test_env_sync_allowlist_membership():
    assert "OPENAI_API_KEY" in env_file_service.ALLOWED_ENV_KEYS
    assert "OPENROUTER_3_API_KEY" in env_file_service.ALLOWED_ENV_KEYS
    assert "EVIL_KEY" not in env_file_service.ALLOWED_ENV_KEYS
    # A sensitive non-allowlisted key must be excluded.
    assert "SECRET_KEY" not in env_file_service.ALLOWED_ENV_KEYS
    assert "DATABASE_URL" not in env_file_service.ALLOWED_ENV_KEYS
