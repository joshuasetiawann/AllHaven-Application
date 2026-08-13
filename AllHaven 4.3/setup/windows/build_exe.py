"""Freeze the Windows setup wizard / control panel into AllHaven-Setup.exe.

PyInstaller bundles CPython itself, so the resulting .exe runs on a machine with
no Python installed — which is the point: the person installing AllHaven should
need nothing but the file they downloaded.

    python setup\\windows\\build_exe.py              # portable .exe only
    python setup\\windows\\build_exe.py --installer  # ...and the Windows installer

Outputs, both in dist\\ :
  AllHaven-Setup.exe            portable — drop it in the AllHaven folder and run it
  AllHaven-Installer-<ver>.exe  full installer with Start Menu entry + uninstaller

The portable build finds the repo by looking for docker-compose.prod.yml beside
itself, so it works from the repo root or from an installed copy.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ENTRY = HERE / "allhaven_windows.py"
NAME = "AllHaven-Setup"


def ensure_pyinstaller() -> bool:
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        pass
    print("PyInstaller is not installed. Installing it now…")
    done = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])  # noqa: S603
    return done.returncode == 0


def main() -> int:
    if not ENTRY.exists():
        print(f"Entry point missing: {ENTRY}")
        return 1
    if not ensure_pyinstaller():
        print("Could not install PyInstaller.")
        return 1

    build_dir = ROOT / "var" / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    argv = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",              # one self-contained file to hand over
        "--console",              # the control panel IS a console UI
        "--name", NAME,
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(build_dir),
        "--specpath", str(build_dir),
        "--noconfirm",
        str(ENTRY),
    ]
    icon = HERE / "allhaven.ico"
    if icon.exists():
        argv[-1:-1] = ["--icon", str(icon)]

    print("Building", NAME + ".exe …")
    if subprocess.run(argv).returncode != 0:  # noqa: S603
        print("Build failed.")
        return 1

    produced = ROOT / "dist" / f"{NAME}.exe"
    if not produced.exists():
        print("Build reported success but the .exe is missing.")
        return 1
    size_mb = produced.stat().st_size / (1024 * 1024)
    print(f"\nBuilt {produced}  ({size_mb:.1f} MB)")

    # A copy at the repo root is what people actually double-click.
    shutil.copy2(produced, ROOT / f"{NAME}.exe")
    print(f"Copied to {ROOT / (NAME + '.exe')}")

    if "--installer" in sys.argv:
        return build_installer()
    return 0


def find_iscc() -> Path | None:
    """Locate the Inno Setup compiler; winget installs it per-user by default."""
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
    ]
    found = shutil.which("ISCC")
    if found:
        candidates.insert(0, Path(found))
    return next((path for path in candidates if path.exists()), None)


def build_installer() -> int:
    iscc = find_iscc()
    if iscc is None:
        print(
            "\nInno Setup is not installed, so the full installer was skipped.\n"
            "  Install it with:  winget install --id JRSoftware.InnoSetup -e\n"
            "  then run this again with --installer."
        )
        return 1
    script = HERE / "AllHaven.iss"
    print(f"\nCompiling the Windows installer with {iscc} …")
    if subprocess.run([str(iscc), str(script)]).returncode != 0:  # noqa: S603
        print("Installer compile failed.")
        return 1
    for produced in sorted((ROOT / "dist").glob("AllHaven-Installer-*.exe")):
        print(f"Built {produced}  ({produced.stat().st_size / (1024 * 1024):.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
