"""Single source of truth for the app version — the repo-root VERSION file.

Used by the FastAPI app metadata, the /health endpoint, and startup logging so the
version never drifts between surfaces (frontend reads its own nav constant; a
consistency test guards them).
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_FALLBACK = "0.0.0"


@lru_cache(maxsize=1)
def get_app_version() -> str:
    """Read the repo-root VERSION file, falling back to ``backend/pyproject.toml``.

    The Docker image is built from ``backend/`` alone, so the repo-root VERSION file
    is not in it and /health used to report 0.0.0 in every container. pyproject.toml
    *is* in the image and ``test_all_version_sources_agree`` keeps the two equal.
    """
    here = Path(__file__).resolve()
    try:
        # backend/app/core/version.py → parents[3] == repo root
        return (here.parents[3] / "VERSION").read_text().strip() or _FALLBACK
    except OSError:
        pass
    try:
        # parents[2] == backend/ (WORKDIR /app in the image)
        found = re.search(r'^version\s*=\s*"([^"]+)"', (here.parents[2] / "pyproject.toml").read_text(), re.M)
        return found.group(1) if found else _FALLBACK
    except OSError:
        return _FALLBACK
