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


def test_supabase_bearer_logout_revokes_bridge_access(client, db_session, supabase_configured):
    _register(client)
    sb_id = _link_supabase_id(db_session)
    token = _make_supabase_token(_SUPABASE_SECRET, _claims(sb_id))
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {token}"}
    assert _get(client, token).status_code == 200

    response = client.post(f"{API}/auth/logout", headers=headers)
    assert response.status_code == 200, response.text
    assert _get(client, token).status_code == 401


def test_supabase_token_no_local_match_rejected(client, db_session, supabase_configured):
    # A Supabase user with no matching local account (neither id nor email) is rejected.
    _register(client)  # owner@example.com exists
    token = _make_supabase_token(
        _SUPABASE_SECRET, _claims(uuid.uuid4(), email="stranger@example.com")
    )
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


def test_supabase_same_email_is_not_auto_linked(client, db_session, supabase_configured):
    # SECURITY: a validly-signed token whose email matches an UNLINKED local profile
    # must NOT be auto-linked. The signature proves Supabase issued the token, not
    # that the bearer owns the email; auto-linking would allow same-email account
    # takeover. The profile must stay unlinked and the request must be rejected.
    _register(client)  # owner@example.com, supabase_user_id unset
    token = _make_supabase_token(_SUPABASE_SECRET, _claims(uuid.uuid4()))  # email == _EMAIL
    assert _get(client, token).status_code == 401
    profile = db_session.query(Profile).filter(Profile.email == _EMAIL).one()
    assert profile.supabase_user_id is None


def test_desktop_token_still_works(auth_client):
    # Regression: the existing SECRET_KEY desktop bearer path is unaffected.
    assert auth_client.get(_AUTHED).status_code == 200


def test_es256_token_is_verified_by_supabase_when_hs256_cannot(client, db_session, monkeypatch):
    """Asymmetric-key projects issue ES256 tokens the stdlib HS256 verifier rejects.

    The backend must fall back to asking Supabase, otherwise Bridge auth is dead for
    every project created with asymmetric JWT signing keys (Supabase's default).
    """
    from app.services import supabase_auth_service

    _register(client)
    sb_id = _link_supabase_id(db_session)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _SUPABASE_SECRET)
    monkeypatch.setattr(
        supabase_auth_service, "get_service_credentials",
        lambda db, workspace_id: ("https://x.supabase.co", "svc"),
    )
    seen: dict = {}

    def fake_verify(url, api_key, token):
        seen["token"] = token
        return str(sb_id)

    monkeypatch.setattr(supabase_auth_service, "verify_access_token", fake_verify)

    es256 = _make_supabase_token("wrong-key", {"sub": str(sb_id), "exp": int(time.time()) + 600}, alg="ES256")
    resp = client.get(_AUTHED, headers={"Authorization": f"Bearer {es256}"})
    assert resp.status_code == 200, resp.text
    assert seen["token"] == es256


def test_es256_token_rejected_when_supabase_says_no(client, db_session, monkeypatch):
    """Supabase declining the token must still be a 401 — no silent pass-through."""
    from app.services import supabase_auth_service

    _register(client)
    _link_supabase_id(db_session)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _SUPABASE_SECRET)
    monkeypatch.setattr(
        supabase_auth_service, "get_service_credentials",
        lambda db, workspace_id: ("https://x.supabase.co", "svc"),
    )
    monkeypatch.setattr(supabase_auth_service, "verify_access_token", lambda u, k, t: None)

    es256 = _make_supabase_token("wrong-key", {"sub": str(uuid.uuid4())}, alg="ES256")
    resp = client.get(_AUTHED, headers={"Authorization": f"Bearer {es256}"})
    assert resp.status_code == 401
