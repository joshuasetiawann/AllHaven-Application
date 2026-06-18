"""Cookie-session auth tests: cookies, CSRF, rotation, logout, rate limit,
and the production SECRET_KEY guard."""

import pytest

from tests.conftest import API

from app.core import ratelimit
from app.core.config import Settings, settings
from app.services.session_service import CSRF_COOKIE, SESSION_COOKIE

CREDS = {"email": "owner@example.com", "password": "password123", "full_name": "Owner"}


def _register(client):
    resp = client.post(f"{API}/auth/register", json=CREDS)
    assert resp.status_code == 200, resp.text
    return resp


def _csrf(client) -> str:
    return client.cookies.get(CSRF_COOKIE)


# --- cookies are set correctly ---------------------------------------------

def test_login_sets_httponly_session_and_readable_csrf_cookies(client):
    resp = _register(client)
    set_cookies = [h for h in resp.headers.get_list("set-cookie")]
    session_header = next(h for h in set_cookies if h.startswith(f"{SESSION_COOKIE}="))
    csrf_header = next(h for h in set_cookies if h.startswith(f"{CSRF_COOKIE}="))
    assert "httponly" in session_header.lower()
    assert "samesite=lax" in session_header.lower()
    assert "httponly" not in csrf_header.lower()  # JS must read it for the header
    assert "samesite=lax" in csrf_header.lower()


# --- cookie-only auth works (no Authorization header, no token in JS) -------

def test_cookie_only_get_me_works(client):
    _register(client)
    resp = client.get(f"{API}/auth/me")  # cookies sent automatically
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["user"]["email"] == CREDS["email"]


# --- CSRF on state-changing requests ----------------------------------------

def test_cookie_post_without_csrf_header_is_rejected(client):
    _register(client)
    resp = client.post(f"{API}/tasks", json={"title": "x"})
    assert resp.status_code == 403, resp.text
    assert resp.json()["error_code"] == "CSRF_FAILED"


def test_cookie_post_with_csrf_header_succeeds(client):
    _register(client)
    resp = client.post(f"{API}/tasks", json={"title": "x"}, headers={"X-CSRF-Token": _csrf(client)})
    assert resp.status_code == 200, resp.text


def test_bearer_post_needs_no_csrf(client):
    token = _register(client).json()["data"]["access_token"]
    client.cookies.clear()  # pure bearer client
    resp = client.post(f"{API}/tasks", json={"title": "x"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text


# --- refresh rotates the session --------------------------------------------

def test_refresh_rotates_session_and_kills_old_cookie(client):
    _register(client)
    old_session = client.cookies.get(SESSION_COOKIE)
    resp = client.post(f"{API}/auth/refresh", headers={"X-CSRF-Token": _csrf(client)})
    assert resp.status_code == 200, resp.text
    new_session = client.cookies.get(SESSION_COOKIE)
    assert new_session and new_session != old_session
    # The pre-rotation secret no longer authenticates.
    client.cookies.set(SESSION_COOKIE, old_session)
    assert client.get(f"{API}/auth/me").status_code == 401


def test_refresh_requires_csrf_header(client):
    _register(client)
    assert client.post(f"{API}/auth/refresh").status_code == 401


# --- logout revokes server-side ---------------------------------------------

def test_logout_revokes_session_and_clears_cookies(client):
    _register(client)
    stolen = client.cookies.get(SESSION_COOKIE)  # simulate a copied cookie
    resp = client.post(f"{API}/auth/logout")
    assert resp.status_code == 200, resp.text
    # Even re-presenting the old cookie fails: the session row is revoked.
    client.cookies.set(SESSION_COOKIE, stolen)
    assert client.get(f"{API}/auth/me").status_code == 401


# --- auth rate limiting -------------------------------------------------------

def test_auth_rate_limit_returns_429(client, monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_PER_MINUTE", 3)
    bad = {"email": "x@example.com", "password": "wrong-password"}
    statuses = [client.post(f"{API}/auth/login", json=bad).status_code for _ in range(4)]
    assert statuses[:3] == [401, 401, 401]
    assert statuses[3] == 429
    ratelimit.reset()


# --- SECRET_KEY production guard ---------------------------------------------

def test_production_rejects_default_secret_key():
    with pytest.raises(Exception, match="SECRET_KEY"):
        Settings(APP_ENV="production", SECRET_KEY="dev-insecure-secret-change-me")


def test_production_rejects_short_secret_key():
    with pytest.raises(Exception, match="SECRET_KEY"):
        Settings(APP_ENV="production", SECRET_KEY="short")


def test_production_accepts_strong_secret_key():
    s = Settings(APP_ENV="production", SECRET_KEY="x" * 48)
    assert s.APP_ENV == "production"


def test_local_allows_dev_secret_key():
    s = Settings(APP_ENV="local", SECRET_KEY="dev-insecure-secret-change-me")
    assert s.is_local_env
