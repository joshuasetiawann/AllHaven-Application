"""Single source of truth for the app version — the repo-root VERSION file.

Used by the FastAPI app metadata, the /health endpoint, and startup logging so the
version never drifts between surfaces (frontend reads its own nav constant; a
consistency test guards them).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_FALLBACK = "0.0.0"


@lru_cache(maxsize=1)
def get_app_version() -> str:
    """Read the repo-root VERSION file (next to the backend/), defaulting safely."""
    try:
        # backend/app/core/version.py → parents[3] == repo root
        return (Path(__file__).resolve().parents[3] / "VERSION").read_text().strip() or _FALLBACK
    except OSError:
        return _FALLBACK
