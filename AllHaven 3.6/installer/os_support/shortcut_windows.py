"""Windows desktop-shortcut helper.

Preferred path: drive a tiny PowerShell script that creates a real ``Haven.lnk``
on the Desktop pointing at the Windows launcher ``.bat`` (with the repo root as
the working directory). If PowerShell is unavailable or fails, fall back to
writing a ``Haven.bat`` on the Desktop that simply calls the launcher.

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
call "{launcher}"
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


def _write_bat_fallback(repo_root: Path, launcher: Path, desktop: Path) -> dict:
    """Fallback: a Haven.bat on the Desktop that calls the launcher."""
    path = desktop / "Haven.bat"
    content = _BAT_TEMPLATE.format(repo_root=str(repo_root), launcher=str(launcher))
    path.write_text(content, encoding="utf-8")
    return {
        "created": True,
        "path": str(path),
        "message": f"Created desktop launcher at {path} (PowerShell shortcut unavailable).",
    }


def create_shortcut(repo_root: Path, app_url: str) -> dict:
    """Create a Windows desktop shortcut to the launcher. Never raises."""
    try:
        repo_root = Path(repo_root)
        launcher = repo_root / "START_HAVEN_WINDOWS.bat"
        desktop = _desktop_dir()

        result = _try_powershell(launcher, repo_root, desktop)
        if result is not None:
            return result

        # PowerShell failed/unavailable — write a .bat launcher instead.
        try:
            return _write_bat_fallback(repo_root, launcher, desktop)
        except OSError as exc:
            return {"created": False, "path": None, "message": f"Could not create shortcut: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"created": False, "path": None, "message": f"Could not create shortcut: {exc}"}
