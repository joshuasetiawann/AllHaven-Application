"""CORS policy regressions."""


def _preflight(client, origin: str):
    return client.options(
        "/api/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )


def test_local_cors_allows_private_lan_tailscale_and_capacitor_origins(client):
    for origin in (
        "http://localhost:3000",
        "https://localhost",
        "capacitor://localhost",
        "http://192.168.1.7:3000",
        "http://100.91.122.124:3000",
        "https://joo.tail01a7d3.ts.net",
    ):
        resp = _preflight(client, origin)

        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == origin
        assert resp.headers["access-control-allow-credentials"] == "true"


def test_local_cors_rejects_public_origins(client):
    resp = _preflight(client, "https://evil.example")

    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers
