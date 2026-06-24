"""CoreOS Command Center — FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.responses import success_response

# Import the domain package so all models are registered on the metadata.
import app.domain  # noqa: F401
from app.api.routers import ai, auth, finance, health, notes, settings as settings_router, tasks


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Modular AI command center — local MVP backend.",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # CORS — restricted to known frontend origins.
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)

    prefix = settings.API_V1_PREFIX
    app.include_router(health.router, prefix=prefix)
    app.include_router(auth.router, prefix=prefix)
    app.include_router(tasks.router, prefix=prefix)
    app.include_router(notes.router, prefix=prefix)
    app.include_router(finance.router, prefix=prefix)
    app.include_router(ai.router, prefix=prefix)
    app.include_router(settings_router.router, prefix=prefix)

    @app.get("/", tags=["root"])
    def root() -> dict:
        return success_response(
            {
                "app": settings.APP_NAME,
                "docs": "/docs",
                "health": f"{prefix}/health",
            },
            "CoreOS API is running",
        )

    return app


app = create_app()
