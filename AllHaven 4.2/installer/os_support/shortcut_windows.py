"""Windows desktop-shortcut helper.

Windows has no shell launcher to commit (``allhaven.sh`` is bash-only); the
Windows entry point is the Python installer/launcher ``installer\\haven_cli.py``,
which installs on first run and starts the services on later runs. This helper
writes a ``Haven.bat`` on the Desktop that invokes it, then (preferred) drives a
tiny PowerShell script to create a real ``Haven.lnk`` pointing at that ``.bat``
(with the repo root as the working directory). If PowerShell is unavailable or
fails, the ``Haven.bat`` itself is the shortcut.

Stdlib only. Everything is guarded — this code may run on a box where it can't
actually be exercised (e.g. this Linux sandbox), so it must import cleanly and
never raise; it returns ``created: False`` with a message instead.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

# PowerShell snippet that builds the .lnk via the WScript.Shell COM object.
# {{ }} are literal braces for str.format; {placeholders} are filled in below.
_PS_TEMPLATE = """$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desktop 'Haven.lnk'
$WScript = New-Object -ComObject WScript.Shell
$shortcut = $WScript.CreateShortcut($lnk)
$shortcut.TargetPath = '{target}'
$shortcut.WorkingDirectory = '{workdir}'
$shortcut.Description = 'Open Haven'
$shortcut.Save()
Write-Output $lnk
"""

_BAT_TEMPLATE = """@echo off
cd /d "{repo_root}"
python installer\\haven_cli.py
if errorlevel 1 pause
"""


def _desktop_dir() -> Path:
    home = Path.home()
    desktop = home / "Desktop"
    return desktop if desktop.is_dir() else home


def _try_powershell(target: Path, workdir: Path, desktop: Path) -> dict | None:
    """Attempt the .lnk approach. Returns a result dict on success, else None."""
    ps_path = None
    try:
        # PowerShell uses single-quoted strings above; escape any embedded quote.
        target_s = str(target).replace("'", "''")
        workdir_s = str(workdir).replace("'", "''")
        script = _PS_TEMPLATE.format(target=target_s, workdir=workdir_s)

        with tempfile.NamedTemporaryFile(
            "w", suffix=".ps1", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(script)
            ps_path = fh.name

        proc = subprocess.run(  # noqa: S603
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path],
            capture_output=True, timeout=30, text=True,
        )
        if proc.returncode == 0:
            lnk = desktop / "Haven.lnk"
            return {
                "created": True,
                "path": str(lnk),
                "message": f"Created desktop shortcut at {lnk}.",
            }
        return None  # signal caller to fall back
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        if ps_path:
            try:
                Path(ps_path).unlink()
            except OSError:
                pass


def _write_desktop_bat(repo_root: Path, desktop: Path) -> Path:
    """Write the Desktop ``Haven.bat`` that launches via the Python installer."""
    path = desktop / "Haven.bat"
    content = _BAT_TEMPLATE.format(repo_root=str(repo_root))
    path.write_text(content, encoding="utf-8")
    return path


def create_shortcut(repo_root: Path, app_url: str) -> dict:
    """Create a Windows desktop shortcut to the launcher. Never raises."""
    try:
        repo_root = Path(repo_root)
        desktop = _desktop_dir()

        # The launcher is the Python installer/launcher; expose it via a Desktop
        # Haven.bat (this is also the fallback shortcut if PowerShell is absent).
        try:
            bat_path = _write_desktop_bat(repo_root, desktop)
        except OSError as exc:
            return {"created": False, "path": None, "message": f"Could not create shortcut: {exc}"}

        # Preferred: a real .lnk pointing at the Haven.bat we just wrote.
        result = _try_powershell(bat_path, repo_root, desktop)
        if result is not None:
            return result

        return {
            "created": True,
            "path": str(bat_path),
            "message": f"Created desktop launcher at {bat_path} (PowerShell shortcut unavailable).",
        }
    except Exception as exc:  # noqa: BLE001
        return {"created": False, "path": None, "message": f"Could not create shortcut: {exc}"}
