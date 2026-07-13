"""Haven launch helper — ensure everything is set up & running, then open the app.

Runs on the first click after setup AND from the desktop shortcut. It is faithful
to the proven ``allhaven.sh`` flow (which is why manual runs work):

  1. ensure dependencies  — backend venv + pip install, frontend npm install
                            (first run only; idempotent and skipped when present)
  2. ensure env files     — frontend/.env.local
  3. start Postgres (Docker) and wait until it accepts connections
  4. ensure the localhost control agent is running
  5. start the backend (the agent runs migrations + binds 0.0.0.0) and wait for /health
  6. start the frontend and wait for its port
  7. open the browser

On any problem it prints a masked tail of the relevant log + clear guidance, so a
failure is visible instead of a silent "backend not reachable". Stdlib only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import haven_common as hc  # noqa: E402


def _say(msg: str) -> None:
    print(msg, flush=True)


def _tail_log(name: str, lines: int = 25) -> str:
    f = hc.logs_dir() / f"{name}.log"
    if not f.exists():
        return ""
    txt = f.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    return hc.mask_secrets("\n".join(txt))


# --- control agent --------------------------------------------------------- #


def _agent_ping() -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(f"{hc.agent_base_url()}/ping", timeout=2) as r:  # noqa: S310
            return r.status == 200
    except OSError:
        return False


def _agent_post(path: str, timeout: float = 130.0) -> tuple[int, dict]:
    import urllib.request

    token = hc.read_token() or ""
    req = urllib.request.Request(
        f"{hc.agent_base_url()}{path}", data=b"{}", method="POST",
        headers={"X-Haven-Token": token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed localhost)
        return r.status, json.loads(r.read().decode("utf-8") or "{}")


def ensure_agent() -> bool:
    if _agent_ping():
        return True
    hc.ensure_dirs()
    hc.ensure_token()
    log = open(hc.logs_dir() / "agent.log", "ab")  # noqa: SIM115
    kwargs: dict = {"stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL,
                    "cwd": str(hc.repo_root()), "env": hc.enriched_env()}
    if os.name == "posix":
        kwargs["start_new_session"] = True
    else:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([hc.venv_python(), str(hc.repo_root() / "installer" / "haven_agent.py")], **kwargs)  # noqa: S603
    import time

    for _ in range(24):
        if _agent_ping():
            return True
        time.sleep(0.5)
    return False


# --- first-run dependency bootstrap (host; may take minutes) --------------- #


def _run(argv: list[str], cwd, log_name: str = "setup") -> int:
    env = hc.enriched_env()
    try:
        with open(hc.logs_dir() / f"{log_name}.log", "ab") as lf:
            lf.write(("\n--- " + " ".join(argv) + " ---\n").encode("utf-8"))
            return subprocess.run(  # noqa: S603 (fixed argv, no shell)
                argv, cwd=str(cwd), env=env, stdout=lf, stderr=subprocess.STDOUT, timeout=1800
            ).returncode
    except (OSError, subprocess.SubprocessError) as exc:
        _say(f"  command failed: {hc.mask_secrets(str(exc))}")
        return 1


def bootstrap() -> None:
    """Install backend/frontend deps if missing. Prints progress; never hard-fails
    (each later step reports its own status)."""
    hc.ensure_dirs()
    hc.ensure_env_files()
    root = hc.repo_root()

    if not hc.backend_setup_ok():
        _say("First run: setting up the backend (Python venv + dependencies). This can take a few minutes…")
        py = "python3" if hc.which("python3") else ("python" if hc.which("python") else sys.executable)
        if _run([py, "-m", "venv", ".venv"], root / "backend") != 0:
            _say("  Could not create the Python virtualenv — is Python 3 installed?")
        else:
            _run([hc.venv_python(), "-m", "pip", "install", "--upgrade", "pip"], root / "backend")
            if _run([hc.venv_python(), "-m", "pip", "install", "-r", "requirements.txt"], root / "backend") != 0:
                _say("  Backend dependency install failed — see var/logs/setup.log")

    if not hc.frontend_setup_ok():
        _say("First run: installing frontend dependencies (npm install). This can take a few minutes…")
        npm = "npm.cmd" if hc.detect_os() == "windows" else "npm"
        if not (hc.which(npm) or hc.which("npm")):
            _say("  npm / Node.js not found on PATH. Install Node 18+ from https://nodejs.org and try again.")
        elif _run([npm, "install"], root / "frontend") != 0:
            _say("  Frontend dependency install failed — see var/logs/setup.log")


# --- main ------------------------------------------------------------------ #


def main() -> int:
    hc.ensure_dirs()
    _say("Starting Haven…")
    bootstrap()

    if not ensure_agent():
        _say("Could not start the Haven control agent. See var/logs/agent.log for details.")
        return 1

    env = hc.read_env()
    be_port = int(env.get("BACKEND_PORT") or hc.default_port("backend") or 8000)
    fe_port = int(env.get("FRONTEND_PORT") or hc.default_port("frontend") or 3000)
    pg_port = int(env.get("POSTGRES_PORT") or hc.default_port("postgres") or 5432)

    # Database
    if hc.docker_running():
        _say("Starting the database (PostgreSQL via Docker; first run pulls the image)…")
        # Run compose directly so the image-pull progress is captured to setup.log
        # (the wizard tails it for live feedback). Idempotent.
        _run(["docker", "compose", "up", "-d", "postgres"], cwd=hc.repo_root())
        _say("  Database is ready." if hc.wait_for_port(pg_port, timeout=60)
             else "  Database not ready yet; continuing (it may still be starting).")
    else:
        _say("Docker isn't running — skipping the database. Start Docker Desktop for full functionality.")

    # Backend (the agent runs migrations, then binds 0.0.0.0)
    _say(f"Starting the backend on port {be_port} (applying migrations)…")
    try:
        _, body = _agent_post("/service/backend/start", timeout=210.0)
        if not body.get("ok", True):
            _say(f"  {body.get('message', '')}")
    except OSError as exc:
        _say(f"  backend: {hc.mask_secrets(str(exc))}")
    if hc.wait_for_http(f"http://127.0.0.1:{be_port}/api/v1/health", timeout=75):
        _say("  Backend is up and healthy.")
    else:
        _say("  Backend did not become healthy in time. Recent backend log:")
        _say(_tail_log("backend") or "    (no backend log yet)")
        _say("  Tip: make sure Docker / the database is running, then run this launcher again.")

    # Frontend — RESTART (not just start) on every launch. `npm run dev`'s predev
    # hook wipes `.next`, so a restart guarantees the latest pulled code is served
    # from a clean cache. This fixes the recurring "desktop loads with no CSS after
    # an update": a stale, already-running dev server kept serving old CSS chunk
    # hashes that no longer existed (404 → unstyled page). Restart is a no-op-safe
    # stop+start whether or not the frontend was already running.
    _say(f"Starting the frontend on port {fe_port} (clean rebuild)…")
    try:
        _, body = _agent_post("/service/frontend/restart", timeout=60.0)
        if not body.get("ok", True):
            _say(f"  {body.get('message', '')}")
    except OSError as exc:
        _say(f"  frontend: {hc.mask_secrets(str(exc))}")
    if hc.wait_for_port(fe_port, timeout=120):
        # `next dev` compiles routes on first request. The port opens before that
        # first compile finishes, so opening the browser immediately can paint an
        # unstyled page (CSS still building). Warm up the landing route and wait for
        # a real 200 so the stylesheet is built BEFORE we open the browser.
        _say("  Frontend is up; warming up the first build (so styles are ready)…")
        hc.wait_for_http(f"http://127.0.0.1:{fe_port}/login", timeout=120)
    else:
        _say("  Frontend not up yet (the first build can take a minute). Recent frontend log:")
        _say(_tail_log("frontend") or "    (no frontend log yet)")

    url = f"http://localhost:{fe_port}"
    _say(f"Opening {url}")
    try:
        webbrowser.open(url)
    except OSError:
        _say(f"Open this address in your browser: {url}")
    _say("Haven is running. You can close this window; services keep running in the background.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
