"""Integration status tests."""

import uuid

from app.core.principal import Principal
from app.core.secrets import encrypt_secret
from app.domain.integrations import IntegrationConfig
from app.services import integration_config_service
from tests.conftest import API


def _make_principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def test_integration_status_is_honest(auth_client):
    resp = auth_client.get(f"{API}/settings/integrations")
    assert resp.status_code == 200, resp.text
    integrations = {i["key"]: i for i in resp.json()["data"]["integrations"]}

    # PostgreSQL is live-checked (SQLite in tests still answers SELECT 1).
    assert integrations["postgresql"]["status"] == "online"

    # Optional integrations are not configured in the test environment.
    for key in ("ollama", "n8n", "supabase", "google_calendar"):
        assert integrations[key]["configured"] is False
        assert integrations[key]["status"] == "not_configured"
        assert integrations[key]["detail"] == "Not configured"


def test_integration_status_requires_auth(client):
    assert client.get(f"{API}/settings/integrations").status_code == 401


def test_empty_supabase_row_does_not_shadow_env_credentials(
    auth_client, db_session, monkeypatch
):
    """Testing Supabase creates a row; an empty row must still inherit .env keys."""

    monkeypatch.setattr(
        integration_config_service.settings,
        "SUPABASE_URL",
        "https://env-project.supabase.co",
        raising=False,
    )
    monkeypatch.setattr(
        integration_config_service.settings,
        "SUPABASE_ANON_KEY",
        "env-anon-key",
        raising=False,
    )
    monkeypatch.setattr(
        integration_config_service.settings,
        "SUPABASE_SERVICE_ROLE_KEY",
        "env-service-role",
        raising=False,
    )
    principal = _make_principal(auth_client)
    db_session.add(
        IntegrationConfig(
            workspace_id=principal.workspace_id,
            provider_id="supabase",
            provider_type="auth_storage",
            display_name="Supabase",
            enabled=True,
            status="configured",
            public_config={},
            encrypted_secrets={},
            created_by=principal.user_id,
        )
    )
    db_session.commit()

    public, secrets = integration_config_service.effective_config(
        db_session, principal, "supabase"
    )
    view = integration_config_service.get_integration(db_session, principal, "supabase")

    assert public["url"] == "https://env-project.supabase.co"
    assert public["anon_key"] == "env-anon-key"
    assert secrets["service_role_key"] == "env-service-role"
    assert view["public_config"]["url"] == "https://env-project.supabase.co"
    assert view["secrets"]["service_role_key"]["configured"] is True


def test_supabase_row_secret_overrides_env_secret(auth_client, db_session, monkeypatch):
    monkeypatch.setattr(
        integration_config_service.settings,
        "SUPABASE_URL",
        "https://env-project.supabase.co",
        raising=False,
    )
    monkeypatch.setattr(
        integration_config_service.settings,
        "SUPABASE_ANON_KEY",
        "env-anon-key",
        raising=False,
    )
    monkeypatch.setattr(
        integration_config_service.settings,
        "SUPABASE_SERVICE_ROLE_KEY",
        "env-service-role",
        raising=False,
    )
    principal = _make_principal(auth_client)
    db_session.add(
        IntegrationConfig(
            workspace_id=principal.workspace_id,
            provider_id="supabase",
            provider_type="auth_storage",
            display_name="Supabase",
            enabled=True,
            status="configured",
            public_config={"url": "https://row-project.supabase.co"},
            encrypted_secrets={"service_role_key": encrypt_secret("row-service-role")},
            created_by=principal.user_id,
        )
    )
    db_session.commit()

    public, secrets = integration_config_service.effective_config(
        db_session, principal, "supabase"
    )

    assert public["url"] == "https://row-project.supabase.co"
    assert public["anon_key"] == "env-anon-key"
    assert secrets["service_role_key"] == "row-service-role"
