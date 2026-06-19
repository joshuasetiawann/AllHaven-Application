"""Google OAuth foundation tests (honest scopes, no fake full-access claims)."""

from tests.conftest import API


def test_google_scopes_are_minimal_and_honest(auth_client):
    resp = auth_client.get(f"{API}/settings/google/scopes")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # Default minimal scopes only — identity, never Gmail by default.
    assert data["default_scopes"] == ["openid", "email", "profile"]
    joined = " ".join(str(data).lower().split())
    assert "gmail" not in " ".join(data["default_scopes"])
    # Catalog exists and marks sensitive scopes; notes explain consent + verification.
    ids = {entry["id"] for entry in data["catalog"]}
    assert {"identity", "calendar_readonly", "drive_readonly"}.issubset(ids)
    assert any("verification" in n.lower() for n in data["notes"])
    assert "all google" not in joined  # never claims full access


def test_google_login_requires_configuration(auth_client):
    # No Google client configured → clean error, not a fake URL.
    resp = auth_client.get(f"{API}/auth/google/login")
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "GOOGLE_NOT_CONFIGURED"


def test_google_appears_in_integrations(auth_client):
    integrations = auth_client.get(f"{API}/settings/integrations").json()["data"]["integrations"]
    google = next((i for i in integrations if i["key"] == "google"), None)
    assert google is not None
    assert google["status"] == "not_configured"


def test_google_configured_is_not_online(auth_client):
    # Saving client config makes it configured — never online without a real OAuth flow.
    auth_client.put(
        f"{API}/settings/integrations/google",
        json={
            "public_config": {"client_id": "abc.apps.googleusercontent.com", "redirect_uri": "http://localhost:3000/cb"},
            "secrets": {"client_secret": "gocspx-demo"},
        },
    )
    data = auth_client.get(f"{API}/settings/integrations/google").json()["data"]
    assert data["status"] == "configured"
    # Building a login URL now works (real consent URL, minimal scopes).
    login = auth_client.get(f"{API}/auth/google/login")
    assert login.status_code == 200
    url = login.json()["data"]["authorization_url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "scope=openid" in url
