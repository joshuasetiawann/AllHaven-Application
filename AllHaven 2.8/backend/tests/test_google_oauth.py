"""Google OAuth foundation tests (honest scopes, no fake full-access claims)."""

from urllib.parse import parse_qs, urlparse

from tests.conftest import API
from app.services import google_oauth as google_oauth_service
from app.services import integration_config_service as integrations_service

CALLBACK_PATH = f"{API}/auth/google/callback"
STATE_COOKIE = "google_oauth_state"


def _configure_google(auth_client):
    resp = auth_client.put(
        f"{API}/settings/integrations/google",
        json={
            "public_config": {"client_id": "abc.apps.googleusercontent.com", "redirect_uri": "http://localhost:3000/cb"},
            "secrets": {"client_secret": "gocspx-demo"},
        },
    )
    assert resp.status_code == 200, resp.text


def _start_login(auth_client) -> str:
    """Run /auth/google/login; return the signed state from the consent URL."""
    login = auth_client.get(f"{API}/auth/google/login")
    assert login.status_code == 200, login.text
    url = login.json()["data"]["authorization_url"]
    return parse_qs(urlparse(url).query)["state"][0]


def _spy_oauth_completion(monkeypatch) -> list:
    """Fake the Google token exchange and record mark_oauth_connected calls."""
    connected: list[str] = []
    monkeypatch.setattr(
        google_oauth_service, "exchange_code",
        lambda code, client_id, client_secret, redirect_uri: (True, {"access_token": "tok"}, ""),
    )
    monkeypatch.setattr(
        integrations_service, "mark_oauth_connected",
        lambda db, principal, provider_id, tokens: connected.append(provider_id),
    )
    return connected


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


# --- Security: callback XSS escaping ----------------------------------------


def test_callback_escapes_error_query_param(client):
    payload = "<script>alert(1)</script>"
    resp = client.get(CALLBACK_PATH, params={"error": payload})
    assert resp.status_code == 400
    assert payload not in resp.text  # raw injection must never render
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in resp.text  # escaped form does


def test_callback_keeps_normal_text_readable(client):
    resp = client.get(CALLBACK_PATH, params={"error": "access_denied"})
    assert resp.status_code == 400
    assert "Google returned: access_denied" in resp.text


# --- Security: OAuth state must be bound to the initiating browser ----------


def test_callback_login_sets_browser_nonce_cookie(auth_client):
    _configure_google(auth_client)
    _start_login(auth_client)
    assert auth_client.cookies.get(STATE_COOKIE)


def test_callback_rejects_missing_browser_cookie(auth_client, monkeypatch):
    _configure_google(auth_client)
    connected = _spy_oauth_completion(monkeypatch)
    state = _start_login(auth_client)
    # A different browser (no nonce cookie) tries to complete a valid signed state.
    auth_client.cookies.clear()
    resp = auth_client.get(CALLBACK_PATH, params={"code": "authcode", "state": state})
    assert resp.status_code == 400
    assert "did not start in this browser" in resp.text
    assert connected == []  # never linked


def test_callback_rejects_mismatched_browser_cookie(auth_client, monkeypatch):
    _configure_google(auth_client)
    connected = _spy_oauth_completion(monkeypatch)
    state = _start_login(auth_client)
    # Wrong nonce in this browser (e.g. a forged link from another flow).
    auth_client.cookies.clear()
    auth_client.cookies.set(STATE_COOKIE, "attacker-nonce", domain="testserver", path=CALLBACK_PATH)
    resp = auth_client.get(CALLBACK_PATH, params={"code": "authcode", "state": state})
    assert resp.status_code == 400
    assert connected == []


def test_callback_with_matching_cookie_connects(auth_client, monkeypatch):
    _configure_google(auth_client)
    connected = _spy_oauth_completion(monkeypatch)
    state = _start_login(auth_client)
    # TestClient kept the HttpOnly nonce cookie from the login response.
    resp = auth_client.get(CALLBACK_PATH, params={"code": "authcode", "state": state})
    assert resp.status_code == 200, resp.text
    assert "Google connected" in resp.text
    assert connected == ["google"]
    # The nonce is single-use: the callback clears the cookie.
    set_cookie = resp.headers.get("set-cookie", "")
    assert STATE_COOKIE in set_cookie and "Max-Age=0" in set_cookie
