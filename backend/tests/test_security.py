"""Security hardening tests: response headers and safe file downloads."""

from fastapi.routing import APIRoute

from app.api.dependencies import get_current_principal
from app.main import app
from tests.conftest import API


_PUBLIC_API_ROUTES = {
    ("GET", f"{API}/health"),
    ("POST", f"{API}/auth/register"),
    ("POST", f"{API}/auth/login"),
    ("POST", f"{API}/auth/refresh"),
    ("POST", f"{API}/auth/logout"),
    ("GET", f"{API}/auth/google/callback"),
}


def _depends_on_current_principal(dependant) -> bool:
    if dependant.call is get_current_principal:
        return True
    return any(_depends_on_current_principal(child) for child in dependant.dependencies)


def test_private_api_routes_require_auth_dependency():
    missing: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith(API):
            continue
        methods = sorted((route.methods or set()) - {"HEAD", "OPTIONS"})
        for method in methods:
            if (method, route.path) in _PUBLIC_API_ROUTES:
                continue
            if not _depends_on_current_principal(route.dependant):
                missing.append(f"{method} {route.path}")

    assert missing == []


def test_security_headers_present(auth_client):
    r = auth_client.get(f"{API}/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert "referrer-policy" in r.headers


def test_drive_config_requires_auth(client):
    r = client.get(f"{API}/drive/config")
    assert r.status_code == 401


def test_drive_download_neutralizes_active_types(auth_client):
    # Upload an HTML file (an inline-XSS vector if served as text/html).
    up = auth_client.post(
        f"{API}/drive/files",
        files={"file": ("evil.html", b"<script>alert(1)</script>", "text/html")},
    )
    assert up.status_code == 200, up.text
    file_id = up.json()["data"]["id"]

    dl = auth_client.get(f"{API}/drive/files/{file_id}/download")
    assert dl.status_code == 200
    # Served as a plain download, never as renderable HTML.
    assert dl.headers["content-type"].startswith("application/octet-stream")
    assert "attachment" in dl.headers.get("content-disposition", "").lower()


def test_drive_rejects_oversized_file(auth_client, monkeypatch):
    import app.services.drive_service as drive
    monkeypatch.setattr(drive, "MAX_FILE_BYTES", 10)
    up = auth_client.post(
        f"{API}/drive/files",
        files={"file": ("big.bin", b"0123456789ABCDEF", "application/octet-stream")},
    )
    assert up.status_code == 422, up.text
