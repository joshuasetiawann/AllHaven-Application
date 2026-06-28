"""Health check router."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.responses import success_response
from app.core.version import get_app_version

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    # Public, unauthenticated reachability probe used by the mobile/desktop
    # Backend Bridge "Test Connection". Returns only safe, non-secret metadata.
    # backend_reachable is trivially True here (you received this response); it
    # exists so the client has an explicit, honest field to gate "online" on.
    return success_response(
        {
            "status": "ok",
            "backend_reachable": True,
            "app": settings.APP_NAME,
            "app_version": get_app_version(),
            "deployment_profile": settings.DEPLOYMENT_PROFILE,
            "env": settings.APP_ENV,
        },
        "Service is healthy",
    )
