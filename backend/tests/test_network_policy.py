"""Server-side integration request network policy."""

from types import SimpleNamespace

from app.core.config import Settings
from app.services.ai_providers import base


class _NoNetworkClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("network client should not be created")


class _FakeResponse:
    status_code = 200
    text = "{}"

    def json(self):
        return {"ok": True}


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def request(self, *args, **kwargs):
        return _FakeResponse()


def test_private_integration_urls_default_to_local_only():
    assert Settings(APP_ENV="local").integration_private_urls_allowed is True
    assert Settings(APP_ENV="production", SECRET_KEY="x" * 48).integration_private_urls_allowed is False
    assert (
        Settings(
            APP_ENV="production",
            SECRET_KEY="x" * 48,
            ALLOW_PRIVATE_INTEGRATION_URLS=True,
        ).integration_private_urls_allowed
        is True
    )


def test_safe_request_blocks_private_urls_when_disabled(monkeypatch):
    monkeypatch.setattr(base, "settings", SimpleNamespace(integration_private_urls_allowed=False))
    monkeypatch.setattr(base.httpx, "Client", _NoNetworkClient)

    code, body, err = base.safe_request("GET", "http://127.0.0.1:8000/api/v1/health")

    assert code is None
    assert body is None
    assert base.NETWORK_BLOCK_MARKER in err


def test_safe_request_blocks_tailscale_shared_ips_when_disabled(monkeypatch):
    monkeypatch.setattr(base, "settings", SimpleNamespace(integration_private_urls_allowed=False))
    monkeypatch.setattr(base.httpx, "Client", _NoNetworkClient)

    code, body, err = base.safe_request("GET", "http://100.91.122.124:8000/api/v1/health")

    assert code is None
    assert body is None
    assert base.NETWORK_BLOCK_MARKER in err


def test_safe_request_allows_private_urls_when_enabled(monkeypatch):
    monkeypatch.setattr(base, "settings", SimpleNamespace(integration_private_urls_allowed=True))
    monkeypatch.setattr(base.httpx, "Client", _FakeClient)

    code, body, err = base.safe_request("GET", "http://127.0.0.1:8000/api/v1/health")

    assert code == 200
    assert body == {"ok": True}
    assert err == ""
