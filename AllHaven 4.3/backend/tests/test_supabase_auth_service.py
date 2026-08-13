"""Supabase Auth provisioning service: credential resolution + admin create_user."""
from __future__ import annotations

import json
import urllib.error
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services import supabase_auth_service


def test_get_service_credentials_env_fallback(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://envproj.supabase.co", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "env-service-role", raising=False)

    url, key = supabase_auth_service.get_service_credentials(db_session, workspace_id=None)
    assert url == "https://envproj.supabase.co"
    assert key == "env-service-role"


def test_get_service_credentials_none_when_unset(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "", raising=False)

    assert supabase_auth_service.get_service_credentials(db_session, workspace_id=None) == (None, None)


def test_create_user_posts_admin_request_with_service_role():
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.get_full_url()
        captured["headers"] = {k.lower(): v for k, v in dict(req.headers).items()}
        captured["body"] = json.loads(req.data.decode())
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.read = lambda: b'{"id": "11111111-1111-1111-1111-111111111111", "email": "x@example.com"}'
        return resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        sb_id = supabase_auth_service.create_user(
            "https://proj.supabase.co",
            "the-service-role-key",
            email="x@example.com",
            password="password123",
            full_name="Ex",
        )

    assert sb_id == "11111111-1111-1111-1111-111111111111"
    assert captured["url"] == "https://proj.supabase.co/auth/v1/admin/users"
    assert captured["headers"]["apikey"] == "the-service-role-key"
    assert captured["headers"]["authorization"] == "Bearer the-service-role-key"
    assert captured["body"]["email"] == "x@example.com"
    assert captured["body"]["email_confirm"] is True
    assert captured["body"]["user_metadata"]["full_name"] == "Ex"


def test_create_user_returns_none_on_http_error():
    def boom(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", side_effect=boom):
        assert (
            supabase_auth_service.create_user(
                "https://proj.supabase.co", "k", email="x@e.com", password="p", full_name=None
            )
            is None
        )


@pytest.mark.parametrize("status_code", [409, 422])
def test_create_user_conflict_never_looks_up_or_resets_existing_user(status_code):
    """An email collision cannot authorize claiming the remote identity."""
    calls: list[str] = []

    def fake_urlopen(req, timeout=None):
        method = req.get_method()
        calls.append(method)
        raise urllib.error.HTTPError(
            req.get_full_url(), status_code, "user already exists", {}, None
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        sb_id = supabase_auth_service.create_user(
            "https://proj.supabase.co",
            "the-service-role-key",
            email="x@example.com",
            password="newpassword",
            full_name=None,
        )

    assert sb_id is None
    assert calls == ["POST"]


def test_access_token_verifier_immediately_honors_authoritative_rejection():
    """A provider-revoked token must not survive in a local acceptance cache."""
    user_id = "11111111-1111-1111-1111-111111111111"
    calls = 0

    def accept_then_reject(req, timeout=None):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise urllib.error.URLError("revoked")
        response = MagicMock()
        response.__enter__ = lambda value: value
        response.__exit__ = MagicMock(return_value=False)
        response.read = lambda: json.dumps({"id": user_id}).encode()
        return response

    with patch("urllib.request.urlopen", side_effect=accept_then_reject):
        assert (
            supabase_auth_service.verify_access_token(
                "https://proj.supabase.co", "key", "redacted-token"
            )
            == user_id
        )
        assert (
            supabase_auth_service.verify_access_token(
                "https://proj.supabase.co", "key", "redacted-token"
            )
            is None
        )
    assert calls == 2

def _seed_user(db_session, *, email, supabase_user_id=None):
    from app.core.security import hash_password
    from app.domain.users import LocalUser, Profile

    uid = uuid.uuid4()
    db_session.add(LocalUser(id=uid, email=email, hashed_password=hash_password("password123")))
    db_session.add(Profile(id=uid, email=email, full_name="Sync User", supabase_user_id=supabase_user_id))
    db_session.commit()
    return uid


def test_sync_password_now_creates_and_links_when_unlinked(db_session, monkeypatch):
    from app.core.config import settings
    from app.domain.users import Profile

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://proj.supabase.co", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "svc", raising=False)
    uid = _seed_user(db_session, email="sync@example.com")

    def fake_urlopen(req, timeout=None):
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.read = lambda: b'{"id": "33333333-3333-3333-3333-333333333333"}'
        return resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        sb_id = supabase_auth_service.sync_password_now(
            db_session, user_id=uid, email="sync@example.com", full_name="Sync User", password="password123"
        )

    assert sb_id == "33333333-3333-3333-3333-333333333333"
    assert str(db_session.get(Profile, uid).supabase_user_id) == "33333333-3333-3333-3333-333333333333"


def test_sync_password_now_resets_password_when_already_linked(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://proj.supabase.co", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "svc", raising=False)
    linked = "44444444-4444-4444-4444-444444444444"
    uid = _seed_user(db_session, email="linked@example.com", supabase_user_id=linked)
    methods: list[str] = []

    def fake_urlopen(req, timeout=None):
        methods.append(req.get_method())
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.read = lambda: b"{}"
        return resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        sb_id = supabase_auth_service.sync_password_now(
            db_session, user_id=uid, email="linked@example.com", full_name="Sync User", password="newpw123"
        )

    assert sb_id == linked
    assert methods == ["PUT"]  # only resets the password; no create/lookup
