"""Security hardening tests: response headers and safe file downloads."""

from tests.conftest import API


def test_security_headers_present(auth_client):
    r = auth_client.get(f"{API}/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert "referrer-policy" in r.headers


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
