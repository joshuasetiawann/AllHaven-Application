"""POST /settings/supabase/connect re-verifies the password then provisions Supabase Auth."""
from __future__ import annotations

from unittest.mock import patch

from tests.conftest import API


def test_connect_supabase_success(auth_client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://proj.supabase.co", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "svc", raising=False)

    with patch(
        "app.services.supabase_auth_service.create_user",
        return_value="33333333-3333-3333-3333-333333333333",
    ) as mock_create:
        resp = auth_client.post(f"{API}/settings/supabase/connect", json={"password": "password123"})

    assert resp.status_code == 200, resp.text
    mock_create.assert_called_once()


def test_connect_supabase_wrong_password(auth_client):
    resp = auth_client.post(f"{API}/settings/supabase/connect", json={"password": "WRONG"})
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 401  # must not log the user out
