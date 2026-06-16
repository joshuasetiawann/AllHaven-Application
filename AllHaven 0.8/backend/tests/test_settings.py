"""Integration status tests."""

from tests.conftest import API


def test_integration_status_is_honest(auth_client):
    resp = auth_client.get(f"{API}/settings/integrations")
    assert resp.status_code == 200, resp.text
    integrations = {i["key"]: i for i in resp.json()["data"]["integrations"]}

    # PostgreSQL is live-checked (SQLite in tests still answers SELECT 1).
    assert integrations["postgresql"]["status"] == "online"

    # Optional integrations are not configured in the test environment.
    for key in ("ollama", "n8n", "supabase", "google_calendar", "weather_api"):
        assert integrations[key]["configured"] is False
        assert integrations[key]["status"] == "not_configured"
        assert integrations[key]["detail"] == "Not configured"


def test_integration_status_requires_auth(client):
    assert client.get(f"{API}/settings/integrations").status_code == 401
