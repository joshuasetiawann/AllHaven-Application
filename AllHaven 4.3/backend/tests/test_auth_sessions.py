"""Cookie-session auth tests: cookies, CSRF, rotation, logout, rate limit,
and the production SECRET_KEY guard."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy.orm import sessionmaker

from tests.conftest import API

from app.core import ratelimit
from app.core.config import Settings, settings
from app.core.database import make_engine
from app.domain.base import Base
from app.domain.users import LocalUser
from app.services import session_service
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


def test_same_old_refresh_cookie_can_rotate_exactly_once(client):
    _register(client)
    old_session = client.cookies.get(SESSION_COOKIE)
    old_csrf = _csrf(client)
    headers = {"X-CSRF-Token": old_csrf}

    first = client.post(f"{API}/auth/refresh", headers=headers)
    assert first.status_code == 200, first.text

    # Re-present the exact pre-rotation pair as a simultaneous loser would.
    client.cookies.set(SESSION_COOKIE, old_session)
    client.cookies.set(CSRF_COOKIE, old_csrf)
    second = client.post(f"{API}/auth/refresh", headers=headers)
    assert second.status_code == 401, second.text


def test_simultaneous_refresh_compare_and_swap_has_one_winner(tmp_path):
    engine = make_engine(f"sqlite+pysqlite:///{tmp_path / 'refresh-race.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        user = LocalUser(email="refresh-race@example.com", hashed_password="unused")
        db.add(user)
        db.flush()
        row, old_raw = session_service.create_session(db, user.id)
        old_csrf = row.csrf_token
        db.commit()

    barrier = Barrier(2)

    def rotate():
        db = sessions()
        try:
            barrier.wait(timeout=5)
            result = session_service.rotate_session(db, old_raw, old_csrf)
            db.commit()
            return result is not None
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _index: rotate(), range(2)))
    assert sorted(outcomes) == [False, True]
    engine.dispose()


def test_logout_revokes_the_presented_bearer_token(client, db_session):
    """A successful bearer logout must make that exact JWT unusable at once."""
    from app.domain.sessions import BearerTokenRevocation

    token = _register(client).json()["data"]["access_token"]
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 200

    response = client.post(f"{API}/auth/logout", headers=headers)
    assert response.status_code == 200, response.text
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401

    row = db_session.query(BearerTokenRevocation).one()
    assert row.token_hash != token
    assert token not in row.token_hash


# --- auth rate limiting -------------------------------------------------------

def test_auth_rate_limit_returns_429(client, monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_PER_MINUTE", 3)
    bad = {"email": "x@example.com", "password": "wrong-password"}
    statuses = [client.post(f"{API}/auth/login", json=bad).status_code for _ in range(4)]
    assert statuses[:3] == [401, 401, 401]
    assert statuses[3] == 429
    ratelimit.reset()


def test_failed_login_bucket_never_blocks_logout(client, monkeypatch):
    _register(client)
    ratelimit.reset()
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_PER_MINUTE", 3)
    bad = {"email": "nobody@example.com", "password": "wrong-password"}
    assert [client.post(f"{API}/auth/login", json=bad).status_code for _ in range(3)] == [
        401,
        401,
        401,
    ]

    response = client.post(f"{API}/auth/logout")
    assert response.status_code == 200, response.text
    assert client.get(f"{API}/auth/me").status_code == 401
    ratelimit.reset()


def test_trusted_proxy_partitions_auth_limit_by_forwarded_client(client, monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_PER_MINUTE", 1)
    # TestClient's direct peer is explicitly trusted for this regression only.
    monkeypatch.setattr(settings, "AUTH_TRUSTED_PROXY_HOSTS", "testclient")
    bad = {"email": "nobody@example.com", "password": "wrong-password"}

    first = client.post(
        f"{API}/auth/login", json=bad, headers={"X-Forwarded-For": "203.0.113.10"}
    )
    same_client = client.post(
        f"{API}/auth/login", json=bad, headers={"X-Forwarded-For": "203.0.113.10"}
    )
    other_client = client.post(
        f"{API}/auth/login", json=bad, headers={"X-Forwarded-For": "203.0.113.11"}
    )
    assert [first.status_code, same_client.status_code, other_client.status_code] == [401, 429, 401]
    ratelimit.reset()


def test_untrusted_peer_cannot_spoof_forwarded_client(client, monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(settings, "AUTH_TRUSTED_PROXY_HOSTS", "")
    bad = {"email": "nobody@example.com", "password": "wrong-password"}
    first = client.post(
        f"{API}/auth/login", json=bad, headers={"X-Forwarded-For": "203.0.113.20"}
    )
    spoofed = client.post(
        f"{API}/auth/login", json=bad, headers={"X-Forwarded-For": "203.0.113.21"}
    )
    assert [first.status_code, spoofed.status_code] == [401, 429]
    ratelimit.reset()


# --- SECRET_KEY production guard ---------------------------------------------

def test_production_rejects_default_secret_key():
    with pytest.raises(Exception, match="SECRET_KEY"):
        Settings(APP_ENV="production", SECRET_KEY="dev-insecure-secret-change-me")


def test_production_rejects_short_secret_key():
    with pytest.raises(Exception, match="SECRET_KEY"):
        Settings(APP_ENV="production", SECRET_KEY="short")


def test_production_accepts_strong_secret_key():
    s = Settings(
        APP_ENV="production",
        SECRET_KEY="x" * 48,
        SETTINGS_ENCRYPTION_KEY="y" * 48,
    )
    assert s.APP_ENV == "production"


def test_production_rejects_default_settings_encryption_key():
    with pytest.raises(Exception, match="SETTINGS_ENCRYPTION_KEY"):
        Settings(APP_ENV="production", SECRET_KEY="x" * 48)


def test_local_allows_dev_secret_key():
    s = Settings(APP_ENV="local", SECRET_KEY="dev-insecure-secret-change-me")
    assert s.is_local_env
