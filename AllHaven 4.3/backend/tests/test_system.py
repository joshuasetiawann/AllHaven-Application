"""Tests for Settings → System Control (authenticated, allowlisted, agent-proxied)."""

from tests.conftest import API

import app.services.system_service as sysmod


def _agent_down(*args, **kwargs):
    raise OSError("agent down")


# --- status --------------------------------------------------------------- #


def test_status_fallback_when_agent_down(auth_client, monkeypatch):
    """With no agent running, status is read-only: nothing controllable."""
    monkeypatch.setattr(sysmod, "_agent", _agent_down)
    data = auth_client.get(f"{API}/system/status").json()["data"]
    assert data["agent"]["running"] is False
    assert data["control_enabled"] is True  # local env in tests
    names = {s["name"] for s in data["services"]}
    assert {"backend", "frontend", "postgres"}.issubset(names)
    assert all(s["controllable"] is False for s in data["services"])


def test_status_uses_agent_when_up(auth_client, monkeypatch):
    fake = {
        "agent": {"running": True, "message": ""},
        "control_enabled": True,
        "services": [{
            "name": "postgres", "label": "PostgreSQL", "kind": "docker",
            "status": "running", "port": 5432, "controllable": True,
            "actions": ["start", "stop", "restart", "logs"], "message": "", "last_checked": "now",
        }],
    }
    monkeypatch.setattr(sysmod, "_agent", lambda *a, **k: (200, fake))
    data = auth_client.get(f"{API}/system/status").json()["data"]
    assert data["agent"]["running"] is True
    assert data["services"][0]["controllable"] is True


def test_status_strips_agent_actions_when_control_is_disabled(auth_client, monkeypatch):
    """An installed agent must not make a read-only deployment look actionable."""
    fake = {
        "agent": {"running": True, "message": ""},
        "control_enabled": True,
        "services": [{
            "name": "postgres", "label": "PostgreSQL", "kind": "docker",
            "status": "running", "port": 5432, "controllable": True,
            "actions": ["start", "stop", "restart", "logs"], "message": "",
            "last_checked": "now",
        }],
    }
    monkeypatch.setattr(sysmod.settings, "APP_ENV", "production")
    monkeypatch.setattr(sysmod, "_agent", lambda *a, **k: (200, fake))

    data = auth_client.get(f"{API}/system/status").json()["data"]

    assert data["control_enabled"] is False
    assert data["agent"]["running"] is False
    assert "not used" in data["agent"]["message"].lower()
    assert data["services"][0]["status"] == "running"
    assert data["services"][0]["controllable"] is False
    assert data["services"][0]["actions"] == []
    assert "read-only" in data["services"][0]["message"].lower()


def test_container_fallback_probes_compose_services_not_its_own_loopback(monkeypatch):
    monkeypatch.setattr(sysmod, "_in_container", lambda: True)
    monkeypatch.setattr(sysmod, "_read_env", lambda: {})
    monkeypatch.setattr(sysmod.settings, "DATABASE_URL", "postgresql+psycopg://u:p@db:5432/allhaven")
    observed = []

    def fake_open(host, port):
        observed.append((host, port))
        return (host, port) in {("frontend", 3000), ("db", 5432)}

    monkeypatch.setattr(sysmod, "_port_open_at", fake_open)
    data = sysmod._fallback_status(enabled=False)
    states = {service["name"]: service["status"] for service in data["services"]}

    assert states == {"backend": "running", "frontend": "running", "postgres": "running"}
    assert ("frontend", 3000) in observed
    assert ("db", 5432) in observed
    assert all(host != "127.0.0.1" for host, _ in observed)


def test_container_fallback_reports_failed_cross_container_probe_as_unknown(monkeypatch):
    monkeypatch.setattr(sysmod, "_in_container", lambda: True)
    monkeypatch.setattr(sysmod, "_read_env", lambda: {})
    monkeypatch.setattr(sysmod, "_port_open_at", lambda *args: False)
    data = sysmod._fallback_status(enabled=False)
    services = {service["name"]: service for service in data["services"]}

    assert services["backend"]["status"] == "running"
    assert services["frontend"]["status"] == "unknown"
    assert services["postgres"]["status"] == "unknown"
    assert "cannot be determined" in services["frontend"]["message"]
    assert "not used" in data["agent"]["message"].lower()


# --- allowlists ----------------------------------------------------------- #


def test_action_rejects_unknown_service(auth_client):
    resp = auth_client.post(f"{API}/system/services/bogus/start")
    assert resp.status_code == 422, resp.text


def test_action_rejects_unknown_action(auth_client):
    assert auth_client.post(f"{API}/system/services/backend/nuke").status_code == 422
    # status/logs are not actions on this endpoint either
    assert auth_client.post(f"{API}/system/services/backend/status").status_code == 422


def test_action_when_agent_down_is_honest(auth_client, monkeypatch):
    monkeypatch.setattr(sysmod, "_agent", _agent_down)
    resp = auth_client.post(f"{API}/system/services/backend/restart")
    assert resp.status_code == 422
    assert "agent" in resp.json()["message"].lower()


def test_action_forwards_to_agent(auth_client, monkeypatch):
    svc = {"name": "postgres", "label": "PostgreSQL", "kind": "docker", "status": "running",
           "port": 5432, "controllable": True, "actions": ["restart"], "message": "", "last_checked": "now"}
    monkeypatch.setattr(sysmod, "_agent", lambda method, path, **k: (200, {"ok": True, "service": svc}))
    data = auth_client.post(f"{API}/system/services/postgres/restart").json()["data"]
    assert data["status"] == "running" and data["name"] == "postgres"


def test_action_surfaces_agent_failure(auth_client, monkeypatch):
    monkeypatch.setattr(sysmod, "_agent", lambda *a, **k: (409, {"ok": False, "message": "docker compose failed."}))
    resp = auth_client.post(f"{API}/system/services/postgres/stop")
    assert resp.status_code == 422
    assert "docker compose failed" in resp.json()["message"]


# --- logs ----------------------------------------------------------------- #


def test_logs_when_agent_down(auth_client, monkeypatch):
    monkeypatch.setattr(sysmod, "_agent", _agent_down)
    resp = auth_client.get(f"{API}/system/logs/backend")
    assert resp.status_code == 422


def test_logs_masks_secrets(auth_client, monkeypatch):
    leaky = "DB_PASSWORD=supersecret\nconnecting postgresql://allhaven:hunter2@localhost:5432/db\nAuthorization: Bearer abc.def.ghi"
    monkeypatch.setattr(sysmod, "_agent", lambda *a, **k: (200, {"name": "backend", "content": leaky, "truncated": False, "message": ""}))
    data = auth_client.get(f"{API}/system/logs/backend?lines=50").json()["data"]
    assert "supersecret" not in data["content"]
    assert "hunter2" not in data["content"]
    assert "abc.def.ghi" not in data["content"]
    assert "***" in data["content"]


# --- ports ---------------------------------------------------------------- #


def test_get_ports(auth_client):
    data = auth_client.get(f"{API}/system/ports").json()["data"]
    assert data["editable"] is True
    assert {"frontend", "backend", "postgres"}.issubset(data["ports"].keys())
    assert data["defaults"]["postgres"] == 5432


def test_save_ports_validates(auth_client):
    assert auth_client.post(f"{API}/system/ports", json={"frontend": 0}).status_code == 422
    assert auth_client.post(f"{API}/system/ports", json={"frontend": 70000}).status_code == 422
    assert auth_client.post(f"{API}/system/ports", json={"frontend": "abc"}).status_code == 422
    # duplicate ports rejected
    assert auth_client.post(f"{API}/system/ports", json={"frontend": 4321, "backend": 4321}).status_code == 422
    # unknown service rejected
    assert auth_client.post(f"{API}/system/ports", json={"mystery": 4321}).status_code == 422


def test_save_ports_writes_env_and_rederives_db_url(auth_client):
    resp = auth_client.post(f"{API}/system/ports", json={"frontend": 3999, "backend": 8999, "postgres": 5999})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["restart_required"] is True
    assert data["applied"] is False  # restart not requested
    assert data["ports"]["postgres"] == 5999
    # The change is persisted and readable back.
    after = auth_client.get(f"{API}/system/ports").json()["data"]["ports"]
    assert after["frontend"] == 3999 and after["postgres"] == 5999

    # DATABASE_URL was re-derived with the new Postgres port (never returned to client).
    from app.core.config import settings
    from pathlib import Path

    env_text = Path(settings.env_file_path).read_text(encoding="utf-8")
    assert ":5999/" in env_text and "POSTGRES_PORT=5999" in env_text


def test_mask_secrets_unit():
    assert sysmod.mask_secrets("SECRET_KEY=abcdef") == "SECRET_KEY=***"
    assert "***" in sysmod.mask_secrets("postgresql://u:p@h:5432/d")
    assert sysmod.mask_secrets("") == ""
