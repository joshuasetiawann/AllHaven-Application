"""System check used by the wizard's Step 3.

Pure detection only (no spawning beyond what ``haven_common`` already does for
docker checks). Safe to import and call anywhere.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import haven_common as hc  # noqa: E402


def system_report() -> dict:
    """Return the Step-3 system check as a plain dict."""
    return {
        "os": hc.detect_os(),
        "docker_installed": hc.docker_installed(),
        "docker_running": hc.docker_running(),
        "compose_available": hc.compose_available(),
        "env_exists": hc.env_path().exists(),
        "compose_file_exists": (hc.repo_root() / "docker-compose.yml").exists(),
        "folders_ok": all((hc.repo_root() / d).is_dir() for d in ("backend", "frontend")),
        "docker_install_url": hc.docker_install_url(),
    }
