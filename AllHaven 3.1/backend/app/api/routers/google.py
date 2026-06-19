"""Google OAuth foundation endpoints.

Honest foundation: builds real consent URLs and exchanges codes when the workspace
has configured a Google OAuth client. Full session login linking is documented as
the next step. Scopes are minimal by default; sensitive scopes require consent and
may require Google app verification in production.
"""

from __future__ import annotations

import hmac
import html
import secrets as _secrets

from fastapi import APIRouter, Cookie, Depends, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.exceptions import BadRequestError
from app.core.principal import Principal
from app.core.responses import success_response
from app.core.security import create_access_token, decode_access_token
from app.services import google_oauth
from app.services import integration_config_service as integrations

router = APIRouter(tags=["google-oauth"])

# Browser-binding nonce for the OAuth flow: set on login, verified + cleared on
# callback. HttpOnly so scripts can't read it; path-limited to the callback.
OAUTH_STATE_COOKIE = "google_oauth_state"
_CALLBACK_PATH = f"{settings.API_V1_PREFIX}/auth/google/callback"


@router.get("/settings/google/scopes")
def google_scopes(principal: Principal = Depends(get_current_principal)) -> dict:
    return success_response(
        {
            "default_scopes": list(google_oauth.DEFAULT_SCOPES),
            "catalog": google_oauth.SCOPE_CATALOG,
            "notes": [
                "One Google login authenticates the user (openid, email, profile).",
                "Each Google app/API needs its own scope and explicit user consent.",
                "Sensitive/restricted scopes may require Google app verification in production.",
                "AllHaven requests minimal scopes by default and never Gmail by default.",
            ],
        },
        "Google OAuth scopes",
    )


@router.get("/auth/google/login")
def google_login(
    response: Response,
    include: str | None = Query(default=None, description="Comma-separated optional scope group ids"),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    public, secrets = integrations.effective_config(db, principal, "google")
    client_id = public.get("client_id")
    redirect_uri = public.get("redirect_uri")
    client_secret = secrets.get("client_secret")
    if not (client_id and redirect_uri and client_secret):
        raise BadRequestError(
            "Google OAuth is not configured. Add your client ID, redirect URI, and client secret "
            "in Settings → Connected Tools → Google OAuth.",
            error_code="GOOGLE_NOT_CONFIGURED",
        )

    include_ids = [s.strip() for s in (include or "").split(",") if s.strip()]
    scopes = google_oauth.resolve_scopes(include_ids)
    # Signed, short-lived state binds the callback to this workspace/user, and a
    # random nonce — mirrored in an HttpOnly cookie — binds it to THIS browser,
    # so a forged or leaked link cannot complete the flow elsewhere.
    nonce = _secrets.token_urlsafe(32)
    state = create_access_token(
        str(principal.workspace_id),
        extra_claims={"uid": str(principal.user_id), "kind": "google_oauth", "nonce": nonce},
        expires_minutes=10,
    )
    url = google_oauth.build_auth_url(client_id, redirect_uri, scopes, state)
    # Same cookie posture as session cookies (see session_service): Lax still
    # rides on Google's top-level redirect back to the callback.
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        nonce,
        max_age=600,
        httponly=True,
        secure=not settings.is_local_env,
        samesite="lax",
        path=_CALLBACK_PATH,
    )
    return success_response(
        {"authorization_url": url, "scopes": scopes},
        "Open this URL to grant Google access",
    )


@router.get("/auth/google/callback", response_class=HTMLResponse)
def google_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    browser_nonce: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE),
) -> HTMLResponse:
    def page(title: str, message: str, ok: bool) -> HTMLResponse:
        # Escape ALL interpolated text: query-parameter-derived values must never
        # reach the page as raw HTML/JS.
        safe_title = html.escape(title)
        safe_message = html.escape(message)
        color = "#34D399" if ok else "#F87171"
        response = HTMLResponse(
            f"""<!doctype html><html><head><meta charset="utf-8"><title>{safe_title}</title>
            <style>body{{background:#0A0C10;color:#E6EAF1;font-family:system-ui;display:flex;
            min-height:100vh;align-items:center;justify-content:center}}.card{{border:1px solid #1F2730;
            border-radius:14px;padding:28px 32px;max-width:420px;text-align:center}}
            h1{{color:{color};font-size:18px}}a{{color:#18E0D6}}</style></head>
            <body><div class="card"><h1>{safe_title}</h1><p>{safe_message}</p>
            <p><a href="/dashboard/settings">Back to AllHaven settings</a></p></div></body></html>""",
            status_code=200 if ok else 400,
        )
        # The nonce is single-use: clear it on success AND failure.
        response.delete_cookie(OAUTH_STATE_COOKIE, path=_CALLBACK_PATH)
        return response

    if error:
        return page("Google sign-in cancelled", f"Google returned: {error}", False)
    if not code or not state:
        return page("Invalid callback", "Missing authorization code or state.", False)

    try:
        payload = decode_access_token(state)
        if payload.get("kind") != "google_oauth":
            raise ValueError("bad state")
        workspace_id = payload.get("sub")
        user_id = payload.get("uid")
        state_nonce = payload.get("nonce")
    except Exception:  # noqa: BLE001
        return page("Invalid callback", "The OAuth state was invalid or expired.", False)

    # Browser binding: the cookie set at /auth/google/login must match the nonce
    # inside the signed state, proving the SAME browser started and is finishing
    # this flow. Reject otherwise — never link a Google account across browsers.
    if (
        not browser_nonce
        or not isinstance(state_nonce, str)
        or not state_nonce
        or not hmac.compare_digest(browser_nonce.encode("utf-8"), state_nonce.encode("utf-8"))
    ):
        return page(
            "Invalid callback",
            "This sign-in did not start in this browser. Please restart the flow from AllHaven settings.",
            False,
        )

    # Build a principal from the trusted state to act on the right workspace.
    import uuid as _uuid

    principal = Principal(
        user_id=_uuid.UUID(str(user_id)),
        workspace_id=_uuid.UUID(str(workspace_id)),
        email="",
        full_name=None,
    )
    db = SessionLocal()
    try:
        public, secrets = integrations.effective_config(db, principal, "google")
        client_id = public.get("client_id")
        redirect_uri = public.get("redirect_uri")
        client_secret = secrets.get("client_secret")
        if not (client_id and redirect_uri and client_secret):
            return page("Not configured", "Google OAuth is not configured for this workspace.", False)
        ok, tokens, err = google_oauth.exchange_code(code, client_id, client_secret, redirect_uri)
        if not ok:
            return page("Could not connect Google", f"Token exchange failed: {err}", False)
        integrations.mark_oauth_connected(db, principal, "google", tokens)
        return page("Google connected", "Your Google account is now linked to this workspace.", True)
    finally:
        db.close()


@router.post("/settings/google/disconnect")
def google_disconnect(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    view = integrations.clear_integration(db, principal, "google")
    return success_response(view, "Google disconnected")
