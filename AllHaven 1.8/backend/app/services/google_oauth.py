"""Google OAuth foundation.

Builds real Google consent URLs and (when configured) exchanges authorization
codes for tokens. Scopes are minimal by default — one Google login authenticates
the user, but each Google API requires its own scope and explicit user consent.
Sensitive/restricted scopes (e.g. Drive write, Gmail) may require Google app
verification before production use.
"""

from __future__ import annotations

from urllib.parse import urlencode

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Default minimal scopes: identity only.
DEFAULT_SCOPES = ("openid", "email", "profile")

# Catalog of optional, scope-gated Google app access (read-only first).
SCOPE_CATALOG = [
    {
        "id": "identity",
        "label": "Sign in (identity)",
        "scopes": list(DEFAULT_SCOPES),
        "sensitive": False,
        "default": True,
        "note": "Authenticate the user and read basic profile (name, email).",
    },
    {
        "id": "calendar_readonly",
        "label": "Google Calendar (read-only)",
        "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
        "sensitive": True,
        "default": False,
        "note": "Read events. Write access is added later, only after explicit approval.",
    },
    {
        "id": "drive_readonly",
        "label": "Google Drive (read-only metadata)",
        "scopes": ["https://www.googleapis.com/auth/drive.metadata.readonly"],
        "sensitive": True,
        "default": False,
        "note": "Read file metadata. Upload/write is added later, only with explicit consent.",
    },
]

_CATALOG_BY_ID = {entry["id"]: entry for entry in SCOPE_CATALOG}


def resolve_scopes(include_ids: list[str] | None) -> list[str]:
    """Return the scope list: always identity, plus any requested optional groups."""
    scopes: list[str] = list(DEFAULT_SCOPES)
    for group_id in include_ids or []:
        entry = _CATALOG_BY_ID.get(group_id)
        if entry:
            for scope in entry["scopes"]:
                if scope not in scopes:
                    scopes.append(scope)
    return scopes


def build_auth_url(client_id: str, redirect_uri: str, scopes: list[str], state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> tuple[bool, dict, str]:
    """Exchange an authorization code for tokens. Returns (ok, tokens, error).

    Google's token endpoint expects a form-encoded body.
    """
    import httpx

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        data = resp.json() if resp.content else {}
        if resp.status_code == 200 and data.get("access_token"):
            return True, data, ""
        return False, {}, str(data.get("error_description") or data.get("error") or f"HTTP {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        return False, {}, str(exc)[:200]
