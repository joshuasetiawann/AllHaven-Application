"""Mobile Backend Bridge auth: the desktop backend accepts Supabase session JWTs.

The mobile app logs in through Supabase and carries a Supabase ``access_token``.
These tests prove ``get_current_principal`` verifies that token with
``SUPABASE_JWT_SECRET`` and maps the Supabase user id to the linked local Profile,
so REST-only Bridge features (Settings, n8n, Ollama, system) work from the phone —
while still rejecting forged, expired, unlinked, and (when unconfigured) all
Supabase tokens. The existing desktop SECRET_KEY token path must keep working.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid

import pytest

from app.core.config import settings
from app.domain.users import Profile
from tests.conftest import API

_SUPABASE_SECRET = "test-supabase-jwt-secret"
_EMAIL = "owner@example.com"
_AUTHED = f"{API}/settings/integrations"  # any auth-gated Bridge endpoint


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _make_supabase_token(secret: str, claims: dict, alg: str = "HS256") -> str:
    header = {"alg": alg, "typ": "JWT"}
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(claims, separators=(",", ":")).encode())
    sig = _b64url(hmac.new(secret.encode("utf-8"), f"{h}.{p}".encode("ascii"), hashlib.sha256).digest())
    return f"{h}.{p}.{sig}"


def _register(client) -> None:
    resp = client.post(
        f"{API}/auth/register",
        json={"email": _EMAIL, "password": "password123", "full_name": "Owner"},
    )
    assert resp.status_code == 200, resp.text


def _link_supabase_id(db_session) -> uuid.UUID:
    profile = db_session.query(Profile).filter(Profile.email == _EMAIL).one()
    sb_id = uuid.uuid4()
    profile.supabase_user_id = sb_id
    db_session.commit()
    return sb_id


def _claims(sb_id: uuid.UUID, **overrides) -> dict:
    base = {
        "sub": str(sb_id),
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "email": _EMAIL,
    }
    base.update(overrides)
    return base


@pytest.fixture
def supabase_configured(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _SUPABASE_SECRET)


def _get(client, token: str):
    return client.get(_AUTHED, headers={"Authorization": f"Bearer {token}"})


def test_supabase_token_authenticates_linked_user(client, db_session, supabase_configured):
    _register(client)
    sb_id = _link_supabase_id(db_session)
    token = _make_supabase_token(_SUPABASE_SECRET, _claims(sb_id))
    assert _get(client, token).status_code == 200


def test_supabase_token_unlinked_user_rejected(client, db_session, supabase_configured):
    _register(client)  # registered, but Profile.supabase_user_id left unset
    token = _make_supabase_token(_SUPABASE_SECRET, _claims(uuid.uuid4()))
    assert _get(client, token).status_code == 401


def test_supabase_token_bad_signature_rejected(client, db_session, supabase_configured):
    _register(client)
    sb_id = _link_supabase_id(db_session)
    token = _make_supabase_token("WRONG-secret", _claims(sb_id))
    assert _get(client, token).status_code == 401


def test_supabase_token_expired_rejected(client, db_session, supabase_configured):
    _register(client)
    sb_id = _link_supabase_id(db_session)
    token = _make_supabase_token(_SUPABASE_SECRET, _claims(sb_id, exp=int(time.time()) - 10))
    assert _get(client, token).status_code == 401


def test_supabase_token_wrong_audience_rejected(client, db_session, supabase_configured):
    _register(client)
    sb_id = _link_supabase_id(db_session)
    token = _make_supabase_token(_SUPABASE_SECRET, _claims(sb_id, aud="anon"))
    assert _get(client, token).status_code == 401


def test_supabase_disabled_when_secret_unset(client, db_session):
    # No SUPABASE_JWT_SECRET configured -> Supabase bearer tokens are not accepted.
    _register(client)
    sb_id = _link_supabase_id(db_session)
    token = _make_supabase_token(_SUPABASE_SECRET, _claims(sb_id))
    assert _get(client, token).status_code == 401


def test_desktop_token_still_works(auth_client):
    # Regression: the existing SECRET_KEY desktop bearer path is unaffected.
    assert auth_client.get(_AUTHED).status_code == 200
