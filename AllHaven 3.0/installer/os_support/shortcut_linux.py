"""Linux desktop-shortcut helper.

Writes a freedesktop ``Haven.desktop`` launcher to ``~/Desktop`` (falling back to
``~/.local/share/applications`` when there is no Desktop folder). The shortcut
runs the Linux launcher script in a terminal.

Stdlib only; everything is guarded so a headless / permission-restricted box
returns a clean ``created: False`` instead of raising.
"""

from __future__ import annotations

from pathlib import Path

_DESKTOP_TEMPLATE = """[Desktop Entry]
Version=1.0
Type=Application
Name=Haven
Comment=Open Haven
Exec=bash "{launcher}"
Path={repo_root}
Terminal=true
Categories=Utility;
"""


def create_shortcut(repo_root: Path, app_url: str) -> dict:
    """Create ``Haven.desktop`` on the Linux desktop. Never raises."""
    try:
        repo_root = Path(repo_root)
        launcher = repo_root / "START_HAVEN_LINUX.sh"

        home = Path.home()
        desktop = home / "Desktop"
        if desktop.is_dir():
            target_dir = desktop
        else:
            target_dir = home / ".local" / "share" / "applications"
            target_dir.mkdir(parents=True, exist_ok=True)

        path = target_dir / "Haven.desktop"
        content = _DESKTOP_TEMPLATE.format(launcher=str(launcher), repo_root=str(repo_root))
        path.write_text(content, encoding="utf-8")
        try:
            path.chmod(0o755)
        except OSError:
            pass  # best effort

        # GNOME requires the launcher to be marked trusted; best-effort only.
        try:
            import subprocess

            subprocess.run(  # noqa: S603,S607
                ["gio", "set", str(path), "metadata::trusted", "true"],
                capture_output=True, timeout=5, text=True,
            )
        except Exception:  # noqa: BLE001 — purely cosmetic, ignore any failure
            pass

        return {
            "created": True,
            "path": str(path),
            "message": f"Created desktop shortcut at {path}.",
        }
    except Exception as exc:  # noqa: BLE001
        return {"created": False, "path": None, "message": f"Could not create shortcut: {exc}"}
