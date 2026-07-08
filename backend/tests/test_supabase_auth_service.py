"""Supabase Auth provisioning service: credential resolution + admin create_user."""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

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
