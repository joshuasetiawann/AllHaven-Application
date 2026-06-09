"""Tests for web-configurable integrations and secret handling."""

import json

from tests.conftest import API


def _register(client, email):
    resp = client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "password123", "full_name": email.split("@")[0]},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def test_missing_config_is_not_configured(auth_client):
    data = auth_client.get(f"{API}/settings/integrations/weather_api").json()["data"]
    assert data["status"] == "not_configured"
    assert data["configured"] is False


def test_saving_secret_masks_and_never_returns_raw(auth_client):
    secret = "owm-supersecret-key-9999"
    resp = auth_client.put(
        f"{API}/settings/integrations/weather_api",
        json={"public_config": {"provider": "openweathermap"}, "secrets": {"api_key": secret}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Saving sets configured, never online.
    assert body["data"]["status"] == "configured"
    assert body["data"]["secrets"]["api_key"]["configured"] is True
    assert body["data"]["secrets"]["api_key"]["preview"]  # masked preview present
    # The raw secret must never appear anywhere in the response.
    assert secret not in json.dumps(body)

    # GET also never returns the raw secret.
    got = auth_client.get(f"{API}/settings/integrations/weather_api")
    assert secret not in json.dumps(got.json())


def test_test_connection_unreachable_is_unavailable(auth_client):
    # Unreachable n8n URL → cannot connect → status unavailable (never online).
    auth_client.put(
        f"{API}/settings/integrations/n8n",
        json={"public_config": {"base_url": "http://127.0.0.1:1"}, "secrets": {}},
    )
    resp = auth_client.post(f"{API}/settings/integrations/n8n/test")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] in ("unavailable", "error")
    assert resp.json()["data"]["status"] != "online"


def test_disable_sets_disabled(auth_client):
    auth_client.put(
        f"{API}/settings/integrations/ollama",
        json={"public_config": {"base_url": "http://localhost:11434"}, "secrets": {}},
    )
    resp = auth_client.post(f"{API}/settings/integrations/ollama/disable")
    assert resp.json()["data"]["status"] == "disabled"
    assert resp.json()["data"]["enabled"] is False
    # Re-enabling restores configured (not online).
    again = auth_client.post(f"{API}/settings/integrations/ollama/enable")
    assert again.json()["data"]["status"] == "configured"


def test_clear_resets_to_not_configured(auth_client):
    auth_client.put(
        f"{API}/settings/integrations/weather_api",
        json={"public_config": {}, "secrets": {"api_key": "abc12345"}},
    )
    auth_client.delete(f"{API}/settings/integrations/weather_api")
    data = auth_client.get(f"{API}/settings/integrations/weather_api").json()["data"]
    assert data["status"] == "not_configured"
    assert data["secrets"]["api_key"]["configured"] is False


def test_system_integration_not_editable(auth_client):
    resp = auth_client.put(
        f"{API}/settings/integrations/postgresql",
        json={"public_config": {"x": "y"}, "secrets": {}},
    )
    assert resp.status_code == 403


def test_integrations_are_workspace_scoped(client):
    token_a = _register(client, "wsa@example.com")
    token_b = _register(client, "wsb@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    client.put(
        f"{API}/settings/integrations/weather_api",
        json={"public_config": {}, "secrets": {"api_key": "secret-a-123"}},
        headers=headers_a,
    )
    # User B must not see user A's configuration.
    data_b = client.get(f"{API}/settings/integrations/weather_api", headers=headers_b).json()["data"]
    assert data_b["status"] == "not_configured"
    data_a = client.get(f"{API}/settings/integrations/weather_api", headers=headers_a).json()["data"]
    assert data_a["status"] == "configured"
