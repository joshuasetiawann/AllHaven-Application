"""macOS desktop-shortcut helper.

Writes a double-clickable ``Haven.command`` to ``~/Desktop`` that execs the macOS
launcher. ``.command`` files open in Terminal on double-click, which is the
simplest no-dependency approach (no .app bundle / codesigning needed).

Stdlib only; guarded so it returns clean data on failure instead of raising.
"""

from __future__ import annotations

from pathlib import Path

_COMMAND_TEMPLATE = """#!/bin/bash
# Haven launcher shortcut — opens Haven.
cd "{repo_root}" || exit 1
exec bash "{launcher}"
"""


def create_shortcut(repo_root: Path, app_url: str) -> dict:
    """Create ``Haven.command`` on the macOS desktop. Never raises."""
    try:
        repo_root = Path(repo_root)
        launcher = repo_root / "START_HAVEN_MAC.command"

        home = Path.home()
        desktop = home / "Desktop"
        if not desktop.is_dir():
            try:
                desktop.mkdir(parents=True, exist_ok=True)
            except OSError:
                desktop = home

        path = desktop / "Haven.command"
        content = _COMMAND_TEMPLATE.format(repo_root=str(repo_root), launcher=str(launcher))
        path.write_text(content, encoding="utf-8")
        try:
            path.chmod(0o755)
        except OSError:
            pass  # best effort

        return {
            "created": True,
            "path": str(path),
            "message": f"Created desktop shortcut at {path}.",
        }
    except Exception as exc:  # noqa: BLE001
        return {"created": False, "path": None, "message": f"Could not create shortcut: {exc}"}
