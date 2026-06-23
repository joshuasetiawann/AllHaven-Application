"""Haven terminal installer — set up and start Haven from the command line.

This is the terminal-first path (no web wizard). It shows **live progress** for the
slow steps — Docker image pull, ``pip install``, ``npm install`` — right in your
terminal, which is what makes the manual flow feel responsive (the web wizard hid
that output, so a first-run image pull looked like it had hung).

Idempotent: safe to run repeatedly. It skips steps already done, then starts the
app and opens the browser. Stdlib only.

Run:  python installer/haven_cli.py
(or, on Linux/macOS, ./install.sh for a fresh install; ./allhaven.sh once set up.)
"""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import haven_common as hc  # noqa: E402

_COLORS = {"ok": "\033[0;32m", "info": "\033[0;36m", "warn": "\033[0;33m",
           "err": "\033[0;31m", "dim": "\033[0;90m", "end": "\033[0m"}


def _use_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None and hc.detect_os() != "windows"


def _c(text: str, kind: str) -> str:
    return f"{_COLORS[kind]}{text}{_COLORS['end']}" if _use_color() else text


def say(msg: str) -> None:
    print(msg, flush=True)


def step(n: int, total: int, msg: str) -> None:
    say(_c(f"\n[{n}/{total}] {msg}", "info"))


def ok(msg: str) -> None:
    say("  " + _c("✓ " + msg, "ok"))


def warn(msg: str) -> None:
    say("  " + _c("! " + msg, "warn"))


def err(msg: str) -> None:
    say("  " + _c("✗ " + msg, "err"))


def _node_install_hint(osname: str) -> str:
    if osname == "macos":
        return "Install Node 18+ from https://nodejs.org or run: brew install node"
    if osname == "linux":
        return "Install Node 18+ from https://nodejs.org or your package manager, then re-run ./install.sh"
    if osname == "windows":
        return "Install Node 18+ from https://nodejs.org, then re-run: python installer\\haven_cli.py"
    return "Install Node 18+ from https://nodejs.org, then run the installer again."


def run_live(argv: list[str], cwd=None) -> int:
    """Run a command with output inherited to this terminal (live progress)."""
    say(_c("  $ " + " ".join(argv), "dim"))
    try:
        return subprocess.run(argv, cwd=str(cwd) if cwd else None, env=hc.enriched_env()).returncode  # noqa: S603
    except FileNotFoundError:
        err(f"command not found: {argv[0]}")
        return 127
    except KeyboardInterrupt:
        raise
    except OSError as exc:
        err(hc.mask_secrets(str(exc)))
        return 1


def _prompt_ports() -> None:
    if not sys.stdin.isatty():
        return
    env = hc.read_env()
    say("  Press Enter to keep each port, or type a new value:")
    updates: dict[str, str] = {}
    for name, default in (("FRONTEND_PORT", "3000"), ("BACKEND_PORT", "8000"), ("POSTGRES_PORT", "5432")):
        cur = env.get(name, default)
        try:
            ans = input(f"    {name} [{cur}]: ").strip()
        except EOFError:
            ans = ""
        if ans:
            if hc.is_valid_port(ans):
                updates[name] = ans
            else:
                warn(f"'{ans}' is not a valid port; keeping {cur}.")
    if updates:
        hc.apply_env_updates(updates)
        ok("Ports updated in .env.")


_TOTAL = 6


def main() -> int:
    hc.ensure_dirs()
    say(_c("\n=== Haven — terminal setup ===", "info"))
    osname = hc.detect_os()

    # 1) Tools
    step(1, _TOTAL, "Checking required tools")
    py_ok = bool(hc.which("python3") or hc.which("python"))
    node_ok = bool(hc.which("node")) and bool(hc.which("npm") or hc.which("npm.cmd"))
    (ok if py_ok else err)("Python 3 " + ("found" if py_ok else "MISSING — install from https://python.org"))
    (ok if node_ok else err)("Node.js + npm " + ("found" if node_ok else "MISSING — install Node 18+ from https://nodejs.org"))
    docker_up = False
    if hc.docker_installed():
        say("  checking the Docker daemon (a few seconds)…")
        docker_up = hc.docker_running()
        (ok if docker_up else warn)("Docker " + ("is running" if docker_up else "installed but NOT running — start Docker Desktop / the service, then re-run"))
    else:
        warn(f"Docker not found — install: {hc.docker_install_url(osname)} (or run a local PostgreSQL on :5432)")
    if not py_ok:
        err("Python 3 is required. Install it and run this again.")
        return 1
    if not node_ok:
        err(_node_install_hint(osname))
        return 1

    # 2) Environment
    step(2, _TOTAL, "Configuring environment (.env + backend/.env)")
    created = hc.ensure_dotenv()["created"]
    ok(".env created with fresh secrets." if created else ".env already exists — keeping it.")
    if created:
        _prompt_ports()
    hc.ensure_env_files()
    ok("backend/.env mirrored from .env; frontend/.env.local ensured.")
    env = hc.read_env()
    fe = int(env.get("FRONTEND_PORT") or 3000)
    be = int(env.get("BACKEND_PORT") or 8000)
    pg = int(env.get("POSTGRES_PORT") or 5432)
    say(_c(f"  ports → frontend {fe} · backend {be} · postgres {pg}", "dim"))

    # 3) Database
    step(3, _TOTAL, "Starting PostgreSQL (Docker)")
    if docker_up:
        say("  first run downloads the postgres image — live progress below:")
        if run_live(["docker", "compose", "up", "-d", "postgres"], cwd=hc.repo_root()) == 0:
            ok("Database ready." if hc.wait_for_port(pg, timeout=60) else "Container up; not accepting connections yet — continuing.")
        else:
            err(f"docker compose failed (see output above). Alternatively run a local PostgreSQL on :{pg}.")
    else:
        warn(f"Skipping Docker. Ensure PostgreSQL is reachable on :{pg} (user/pass/db = allhaven).")

    # 4) Backend deps + migrations
    step(4, _TOTAL, "Backend (virtualenv + dependencies + migrations)")
    backend = hc.repo_root() / "backend"
    if not hc.backend_setup_ok():
        py = "python3" if hc.which("python3") else "python"
        if run_live([py, "-m", "venv", ".venv"], cwd=backend) != 0:
            err("Could not create the Python virtualenv.")
        else:
            run_live([hc.venv_python(), "-m", "pip", "install", "--upgrade", "pip"], cwd=backend)
            if run_live([hc.venv_python(), "-m", "pip", "install", "-r", "requirements.txt"], cwd=backend) == 0:
                ok("Backend dependencies installed.")
            else:
                err("Backend dependency install failed (see output above).")
    else:
        ok("Backend virtualenv already present.")
    say("  applying migrations (alembic upgrade head):")
    if run_live([hc.venv_python(), "-m", "alembic", "upgrade", "head"], cwd=backend) == 0:
        ok("Migrations applied.")
    else:
        warn("Migrations did not complete — is the database running? You can re-run this installer.")

    # 5) Frontend deps
    step(5, _TOTAL, "Frontend dependencies")
    if not hc.frontend_setup_ok():
        npm = "npm.cmd" if osname == "windows" else "npm"
        if not (hc.which(npm) or hc.which("npm")):
            err("npm / Node.js not found — install Node 18+ and run this again.")
        elif run_live([npm, "install"], cwd=hc.repo_root() / "frontend") == 0:
            ok("Frontend dependencies installed.")
        else:
            err("Frontend dependency install failed (see output above).")
    else:
        ok("Frontend node_modules already present.")

    # 6) Start everything + open the browser (reuses the proven launcher)
    step(6, _TOTAL, "Starting Haven")
    import haven_launch

    return haven_launch.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        say("\nCancelled.")
        raise SystemExit(130)
