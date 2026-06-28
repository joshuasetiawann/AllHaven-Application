"""register_user provisions a Supabase Auth user when env creds are set; no-op otherwise."""
from __future__ import annotations

import uuid
from unittest.mock import patch

from app.services import auth_service


def test_register_provisions_and_stores_supabase_id(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://proj.supabase.co", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "svc", raising=False)
    sb_id = "22222222-2222-2222-2222-222222222222"

    with patch("app.services.supabase_auth_service.create_user", return_value=sb_id) as mock_create:
        user, workspace = auth_service.register_user(
            db_session, email="prov@example.com", password="password123", full_name="Prov"
        )

    mock_create.assert_called_once()
    from app.domain.users import Profile

    profile = db_session.get(Profile, user.id)
    assert str(profile.supabase_user_id) == sb_id


def test_register_no_supabase_when_unconfigured(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "", raising=False)

    with patch("app.services.supabase_auth_service.create_user") as mock_create:
        user, _ = auth_service.register_user(
            db_session, email="noprov@example.com", password="password123", full_name="No"
        )

    mock_create.assert_not_called()
    from app.domain.users import Profile

    assert db_session.get(Profile, user.id).supabase_user_id is None


def test_register_survives_supabase_failure(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://proj.supabase.co", raising=False)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "svc", raising=False)

    with patch("app.services.supabase_auth_service.create_user", return_value=None):
        user, _ = auth_service.register_user(
            db_session, email="fail@example.com", password="password123", full_name="Fail"
        )

    assert user.id is not None  # local registration still committed
