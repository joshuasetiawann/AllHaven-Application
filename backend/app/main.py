"""AllHaven Command Center — FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.ratelimit import auth_rate_limit_middleware
from app.core.responses import success_response


from app.core.version import get_app_version as _app_version  # single source of truth

# Import the domain package so all models are registered on the metadata.
import app.domain  # noqa: F401
from app.api.routers import (
    ai,
    auth,
    automations,
    calendar,
    drive,
    finance,
    google,
    health,
    memory,
    knowledge,
    n8n,
    notes,
    routines,
    settings as settings_router,
    system,
    tasks,
)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Run the two-way Supabase sync continuously so phone-side changes are
        # pulled even while the desktop is idle (the per-write trigger only fires
        # on desktop writes). No-op when Supabase isn't configured.
        from app.services import sync_scheduler

        sync_scheduler.start(settings.SYNC_INTERVAL_SECONDS)
        try:
            yield
        finally:
            await sync_scheduler.stop()

    app = FastAPI(
        title=settings.APP_NAME,
        version=_app_version(),
        description="Modular AI command center — local MVP backend.",
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
        lifespan=lifespan,
    )

    # Security headers on every response (defense in depth). No CSP here so the
    # Swagger UI at /docs keeps working; the frontend sets its own CSP.
    @app.middleware("http")
    async def _security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        return response

    # CORS. Browser auth is an HttpOnly SameSite=Lax cookie, so credentials must
    # be allowed for trusted frontend origins. Local/dev accepts localhost,
    # private LAN IPs, Tailscale CGNAT IPs, Tailscale Serve hostnames, and the
    # Capacitor WebView origin. It does not echo arbitrary public origins unless
    # BACKEND_CORS_ALLOW_ALL is explicitly enabled.
    if settings.BACKEND_CORS_ALLOW_ALL:
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=".*",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    elif settings.is_local_env:
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=settings.cors_private_origin_regex,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    elif settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Per-IP rate limit on /auth/* POSTs (enabled via AUTH_RATE_LIMIT_PER_MINUTE).
    app.middleware("http")(auth_rate_limit_middleware)

    register_exception_handlers(app)

    prefix = settings.API_V1_PREFIX
    app.include_router(health.router, prefix=prefix)
    app.include_router(auth.router, prefix=prefix)
    app.include_router(tasks.router, prefix=prefix)
    app.include_router(notes.router, prefix=prefix)
    app.include_router(finance.router, prefix=prefix)
    app.include_router(ai.router, prefix=prefix)
    app.include_router(memory.router, prefix=prefix)
    app.include_router(knowledge.router, prefix=prefix)
    app.include_router(settings_router.router, prefix=prefix)
    app.include_router(google.router, prefix=prefix)
    app.include_router(calendar.router, prefix=prefix)
    app.include_router(routines.router, prefix=prefix)
    app.include_router(drive.router, prefix=prefix)
    app.include_router(automations.router, prefix=prefix)
    app.include_router(n8n.router, prefix=prefix)
    app.include_router(system.router, prefix=prefix)

    @app.get("/", tags=["root"])
    def root() -> dict:
        data = {
            "app": settings.APP_NAME,
            "health": f"{prefix}/health",
        }
        if settings.api_docs_enabled:
            data["docs"] = "/docs"
        return success_response(
            data,
            "AllHaven API is running",
        )

    return app


app = create_app()
