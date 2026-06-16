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


def _ensure_backend_venv(backend) -> str:
    """Create or repair the backend venv and install dependencies INTO it.

    Returns a status word for the summary: 'ready' | 'repaired' | 'failed'.
    Safe and idempotent: a broken venv is renamed aside (never deleted), a fresh
    one is created, and deps are installed only when they don't already import.
    """
    repaired = False
    # A venv whose interpreter can't run can't be fixed by pip — quarantine it
    # (rename, never delete) and rebuild. A merely depless venv is NOT broken.
    if hc.backend_venv_broken():
        moved = hc.quarantine_broken_venv()
        if moved:
            warn(f"backend/.venv looked broken (its Python won't run) — moved to {moved} and recreating.")
            repaired = True
        else:
            err("backend/.venv looks broken but couldn't be moved aside — rename it yourself and re-run.")
            return "failed"

    if not hc.venv_python_path().exists():
        py = "python3" if hc.which("python3") else "python"
        if run_live([py, "-m", "venv", ".venv"], cwd=backend) != 0 or not hc.venv_python_path().exists():
            err("Could not create the Python virtualenv. The 'venv' module may be missing — "
                "on Debian/Ubuntu install it with 'sudo apt install python3-venv' (run that "
                "yourself; this installer never uses sudo), then re-run.")
            return "failed"

    if hc.venv_deps_ok():
        ok("Backend virtualenv is valid (dependencies import cleanly).")
        return "repaired" if repaired else "ready"

    run_live([hc.venv_python(), "-m", "pip", "install", "--upgrade", "pip"], cwd=backend)
    if run_live([hc.venv_python(), "-m", "pip", "install", "-r", "requirements.txt"], cwd=backend) == 0 and hc.venv_deps_ok():
        ok("Backend dependencies installed.")
        return "repaired" if repaired else "ready"
    err("Backend dependency install failed (see output above).")
    return "failed"


def _final_summary(pg: int, be: int, fe: int, venv_status: str, migration_ok: bool) -> None:
    """Print a clear, honest end-of-run report. Reads live state; never fakes it."""
    import urllib.request

    def _http_ok(url: str) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:  # noqa: S310 (localhost)
                return 200 <= r.status < 300
        except OSError:
            return False

    db_ok = hc.port_in_use(pg)
    backend_ok = _http_ok(f"http://127.0.0.1:{be}/api/v1/health")
    frontend_ok = hc.port_in_use(fe)
    venv_ok = hc.venv_deps_ok()

    def line(label: str, value: str, good: bool) -> None:
        mark = _c("✓", "ok") if good else _c("•", "warn")
        say(f"  {mark} {label:<11} {value}")

    say(_c("\n=== AllHaven — setup summary ===", "info"))
    line("PostgreSQL", f":{pg} " + ("reachable" if db_ok else "NOT reachable"), db_ok)
    line("Database", "connection OK" if db_ok else "no server on the port yet", db_ok)
    line("Virtualenv", "valid" if venv_ok else ("repaired" if venv_status == "repaired" else "needs attention — re-run installer"), venv_ok)
    line("Migrations", "applied (alembic head)" if migration_ok else "not confirmed — re-run after the DB is up", migration_ok)
    line("Backend", f"http://localhost:{be}  " + ("healthy" if backend_ok else "not healthy yet"), backend_ok)
    line("Frontend", f"http://localhost:{fe}  " + ("up" if frontend_ok else "not up yet"), frontend_ok)
    if not (db_ok and backend_ok):
        say(_c("  Next: ensure PostgreSQL is running, then re-run ./install.sh (idempotent) "
               "or ./allhaven.sh restart. Diagnose anytime with ./scripts/doctor.sh.", "dim"))


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

    # 3) Database — detect an existing PostgreSQL FIRST, so we never fight a
    #    native server (or a leftover container) by trying to bind a busy port.
    step(3, _TOTAL, "PostgreSQL database")
    if hc.port_in_use(pg):
        ok(f"PostgreSQL already listening on :{pg} — using it. No second database is "
           f"started, so existing data is untouched.")
        say(_c(f"  (If that's a different app's PostgreSQL, set POSTGRES_PORT to a free "
               f"port in .env and re-run.)", "dim"))
    elif docker_up:
        say("  starting PostgreSQL via Docker (first run downloads the image — live progress below):")
        if run_live(["docker", "compose", "up", "-d", "postgres"], cwd=hc.repo_root()) == 0:
            ok("Database ready." if hc.wait_for_port(pg, timeout=60)
               else "Container up; not accepting connections yet — continuing.")
        else:
            free = hc.suggest_free_port(pg + 1) or (pg + 1)
            err(f"Docker could not start PostgreSQL on :{pg}.")
            say(_c(f"  Fix: free port {pg}, OR set POSTGRES_PORT={free} in .env (it is backed "
                   f"up automatically) and re-run. No data volume is removed.", "dim"))
    else:
        warn(f"No PostgreSQL on :{pg} and Docker isn't running.")
        say(_c(f"  Start Docker Desktop / the service, or run a local PostgreSQL on :{pg} "
               f"(user/pass/db = allhaven), then re-run.", "dim"))

    # 4) Backend deps + migrations
    step(4, _TOTAL, "Backend (virtualenv + dependencies + migrations)")
    backend = hc.repo_root() / "backend"
    venv_status = _ensure_backend_venv(backend)
    migration_ok = False
    if venv_status == "failed":
        warn("Skipping migrations until the virtualenv is fixed (see messages above).")
    else:
        say("  applying migrations (alembic upgrade head, through the venv):")
        if run_live(hc.venv_alembic_argv("upgrade", "head"), cwd=backend) == 0:
            ok("Migrations applied.")
            migration_ok = True
        else:
            warn(f"Migrations did not complete — is PostgreSQL running on :{pg}? "
                 "Fix that and re-run; nothing was deleted.")

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

    rc = haven_launch.main()
    _final_summary(pg, be, fe, venv_status, migration_ok)
    return rc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        say("\nCancelled.")
        raise SystemExit(130)
