"""Standard API response envelopes.

Every successful endpoint returns the success envelope and every handled error
returns the error envelope, so the frontend can rely on a single shape.
"""

from __future__ import annotations

from typing import Any, Optional


def success_response(
    data: Any = None,
    message: str = "Operation completed successfully",
) -> dict:
    """Build the standard success envelope."""
    return {"status": "success", "data": data, "message": message}


def error_response(
    error_code: str,
    message: str,
    details: Optional[dict] = None,
) -> dict:
    """Build the standard error envelope."""
    return {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "details": details or {},
    }
