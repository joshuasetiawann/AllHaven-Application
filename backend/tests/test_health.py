"""Health endpoint tests."""

from tests.conftest import API


def test_health_ok(client):
    resp = client.get(f"{API}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["status"] == "ok"


def test_health_reports_backend_reachable(client):
    # The Backend Bridge "Test Connection" gates "online" on a real /health
    # success carrying this field — it must be present and truthy.
    resp = client.get(f"{API}/health")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["backend_reachable"] is True


def test_health_leaks_no_secrets(client):
    # /health is public and unauthenticated — it must never expose secrets.
    resp = client.get(f"{API}/health")
    raw = resp.text.lower()
    for needle in (
        "secret_key",
        "encryption_key",
        "api_key",
        "password",
        "service_role",
        "test-secret-key",
        "test-encryption-key",
    ):
        assert needle not in raw, f"/health leaked '{needle}'"


def test_root_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
