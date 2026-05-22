"""Application exceptions and centralized exception handlers.

Handlers convert exceptions into the standard error envelope and never leak raw
stack traces to clients.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.responses import error_response

logger = logging.getLogger("coreos")


class AppException(Exception):
    """Base class for all expected application errors."""

    status_code: int = 400
    error_code: str = "BAD_REQUEST"

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        self.details = details or {}


class BadRequestError(AppException):
    status_code = 400
    error_code = "BAD_REQUEST"


class UnauthorizedError(AppException):
    status_code = 401
    error_code = "UNAUTHORIZED"


class ForbiddenError(AppException):
    status_code = 403
    error_code = "FORBIDDEN"


class NotFoundError(AppException):
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(AppException):
    status_code = 409
    error_code = "CONFLICT"


class ValidationAppError(AppException):
    status_code = 422
    error_code = "VALIDATION_ERROR"


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app."""

    @app.exception_handler(AppException)
    async def _handle_app_exception(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(exc.error_code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Build a JSON-safe error list (Pydantic's raw ctx may hold exceptions).
        errors = [
            {
                "loc": [str(part) for part in err.get("loc", [])],
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_response(
                "VALIDATION_ERROR",
                "Request validation failed.",
                {"errors": errors},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code_map = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND"}
        error_code = code_map.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(error_code, message),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Log the real error server-side; never expose internals to the client.
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=error_response(
                "INTERNAL_ERROR",
                "An unexpected error occurred.",
            ),
        )
