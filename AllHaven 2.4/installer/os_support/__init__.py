"""OS-specific desktop-shortcut helpers for the Haven setup wizard.

Stdlib only. This package dispatches to a per-OS ``create_shortcut`` based on
``hc.detect_os()``. Every entry point is defensive: shortcut creation can run on
machines without a desktop, without PowerShell, or with restricted permissions,
so failures are caught and returned as data — never raised.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import haven_common as hc  # noqa: E402


def create_desktop_shortcut(app_url: str) -> dict:
    """Create an OS-appropriate desktop shortcut that launches Haven.

    Picks the right module from ``hc.detect_os()`` and calls its
    ``create_shortcut(repo_root, app_url)``. Always returns a dict shaped like
    ``{"created": bool, "path": str | None, "message": str}`` and never raises.
    """
    try:
        os_name = hc.detect_os()
        if os_name == "windows":
            from . import shortcut_windows as mod
        elif os_name == "macos":
            from . import shortcut_macos as mod
        else:  # linux / unknown -> linux
            from . import shortcut_linux as mod
        result = mod.create_shortcut(hc.repo_root(), app_url)
        # Normalise: guarantee the documented keys exist.
        return {
            "created": bool(result.get("created", False)),
            "path": result.get("path"),
            "message": str(result.get("message", "")),
        }
    except Exception as exc:  # noqa: BLE001 — never raise to the caller
        return {"created": False, "path": None, "message": str(exc)}
