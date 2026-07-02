"""Health check router."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.responses import success_response

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return success_response(
        {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV},
        "Service is healthy",
    )
