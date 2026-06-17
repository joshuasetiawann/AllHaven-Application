"""Haven first-run setup wizard — a localhost-only, token-gated web server.

This serves a single-page guided wizard (``installer/web/index.html``) that walks
a brand-new user through:

    System check -> Docker help -> Ports -> Write .env -> Start services
    -> Start agent -> Health -> Desktop shortcut -> Finish.

Security model (all enforced here):
    * Binds 127.0.0.1 ONLY — never reachable off the machine.
    * A random per-run URL token is generated at startup, injected into the page,
      and required (header ``X-Setup-Token``, constant-time compared) on every
      ``/api/*`` request. Without it, endpoints return 403. This is SEPARATE from
      the long-lived agent token in ``var/agent/token``.
    * No shell, ever. Docker is driven via an argv list of the single
      non-destructive command ``docker compose up -d postgres``.
    * Secret values are never returned; output is passed through
      ``hc.mask_secrets`` before being shown.
    * ``apply_env_updates`` backs up ``.env`` and preserves existing secrets.

Stdlib only. Run with:  python installer/haven_setup.py
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import haven_common as hc  # noqa: E402
from os_support import create_desktop_shortcut  # noqa: E402
from os_support import detect as os_detect  # noqa: E402

POSIX = os.name == "posix"
SETUP_HOST = "127.0.0.1"  # localhost ONLY — never bind 0.0.0.0
_PORT_SERVICES = ("frontend", "backend", "postgres")

# Per-run URL token, set in serve(). Guards every /api/* request.
SETUP_TOKEN: str = ""


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _configured_or_default_port(name: str) -> int | None:
    """Current value from .env if valid, else the registry default."""
    env = hc.read_env()
    key = hc.port_env_key(name)
    if key and key in env and hc.is_valid_port(env[key]):
        return int(env[key])
    return hc.default_port(name)


def _current_ports() -> dict:
    """The three wizard-managed ports, from .env or defaults."""
    return {name: _configured_or_default_port(name) for name in _PORT_SERVICES}


def _coerce_ports(body: dict) -> dict:
    """Pull frontend/backend/postgres out of a request body as-is (unvalidated)."""
    ports = body.get("ports", body) or {}
    return {name: ports.get(name) for name in _PORT_SERVICES if name in ports}


def _http_ok(url: str, timeout: float = 1.2) -> bool:
    """True if a localhost GET returns a 2xx/3xx/4xx (i.e. *something* answered).

    For health we treat any HTTP response as "the server is up". Connection
    refused / timeout => down.
    """
    try:
        with urlopen(url, timeout=timeout) as resp:  # noqa: S310 — localhost only
            return 200 <= resp.status < 500
    except Exception:  # noqa: BLE001 — any failure means "not up"
        return False


# --------------------------------------------------------------------------- #
# API endpoint implementations (pure-ish; return JSON-able dicts)
# --------------------------------------------------------------------------- #


def api_detect() -> dict:
    report = os_detect.system_report()
    report["ports"] = _current_ports()
    return report


def api_ports_suggest(body: dict) -> dict:
    ports = _coerce_ports(body)
    errors = hc.validate_ports(ports)
    suggestions: dict[str, int] = {}
    # Propose a free port for anything that is valid but already in use,
    # avoiding collisions with the other requested ports.
    taken = {int(v) for v in ports.values() if hc.is_valid_port(v)}
    for name, value in ports.items():
        if name in errors:
            continue
        if hc.is_valid_port(value) and hc.port_in_use(int(value)):
            errors[name] = f"Port {int(value)} is already in use."
            free = hc.suggest_free_port(int(value) + 1, taken=taken)
            if free is not None:
                suggestions[name] = free
                taken.add(free)
    return {"errors": errors, "suggestions": suggestions}


def _build_secret_updates(env: dict) -> dict:
    """Generate SECRET_KEY / SETTINGS_ENCRYPTION_KEY only if missing/placeholder."""
    updates: dict[str, str] = {}

    def _needs(key: str) -> bool:
        val = (env.get(key) or "").strip()
        return (not val) or ("change-me" in val.lower())

    if _needs("SECRET_KEY"):
        updates["SECRET_KEY"] = secrets.token_urlsafe(48)
    if _needs("SETTINGS_ENCRYPTION_KEY"):
        updates["SETTINGS_ENCRYPTION_KEY"] = secrets.token_urlsafe(32)
    return updates


def _database_url(env: dict, ports: dict) -> str:
    """Assemble DATABASE_URL from existing .env values + the chosen postgres port."""
    user = env.get("POSTGRES_USER") or "allhaven"
    password = env.get("POSTGRES_PASSWORD") or "allhaven"
    host = env.get("POSTGRES_HOST") or "localhost"
    db = env.get("POSTGRES_DB") or "allhaven"
    port = int(ports["postgres"])
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def api_env_apply(body: dict) -> dict:
    ports = _coerce_ports(body)
    errors = hc.validate_ports(ports)
    if errors:
        return {"ok": False, "errors": errors, "message": "Fix the port errors before writing .env."}

    # Read current values to (a) preserve secrets and (b) assemble DATABASE_URL.
    env = hc.read_env()

    updates: dict[str, str] = {}
    # Map each managed service to its POSTGRES_PORT/BACKEND_PORT/FRONTEND_PORT key.
    for name, value in ports.items():
        key = hc.port_env_key(name)
        if key:
            updates[key] = str(int(value))

    # Ensure mandatory secrets exist (generate if missing/placeholder).
    updates.update(_build_secret_updates(env))

    # If a postgres port was chosen, keep DATABASE_URL consistent with it.
    if "postgres" in ports and hc.is_valid_port(ports["postgres"]):
        updates["DATABASE_URL"] = _database_url(env, ports)

    result = hc.apply_env_updates(updates)
    # NEVER return secret values — only the key names that changed.
    return {
        "ok": True,
        "backup": result.get("backup"),
        "created": result.get("created", False),
        "updated_keys": result.get("updated_keys", []),
        "message": "Wrote .env. Existing secrets were preserved; new ones generated where missing.",
    }


def api_agent_start() -> dict:
    """Start haven_agent.py detached, then poll its /ping for up to ~10s."""
    hc.ensure_dirs()
    agent_script = hc.repo_root() / "installer" / "haven_agent.py"
    if not agent_script.exists():
        return {"ok": False, "message": f"Agent script not found at {agent_script}."}

    python_exe = hc.venv_python() or sys.executable
    log_path = hc.logs_dir() / "agent.log"
    try:
        logf = open(log_path, "ab", buffering=0)  # noqa: SIM115 — handed to child
    except OSError as exc:
        return {"ok": False, "message": f"Could not open agent log: {hc.mask_secrets(str(exc))}"}

    kwargs: dict = {
        "stdout": logf,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
        "cwd": str(hc.repo_root()),
    }
    if POSIX:
        kwargs["start_new_session"] = True  # detach into its own session
    else:  # Windows
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    try:
        subprocess.Popen([python_exe, str(agent_script)], **kwargs)  # noqa: S603 — argv list, no shell
    except (OSError, ValueError) as exc:
        return {"ok": False, "message": f"Could not start agent: {hc.mask_secrets(str(exc))}"}
    finally:
        try:
            logf.close()  # child keeps its own dup'd handle
        except OSError:
            pass

    ping_url = f"{hc.agent_base_url()}/ping"
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if _http_ok(ping_url, timeout=1.0):
            return {"ok": True, "message": f"Agent is running at {hc.agent_base_url()}."}
        time.sleep(0.5)
    return {
        "ok": False,
        "message": "Agent did not respond on /ping within 10s. Check var/logs/agent.log.",
    }


def _mask_tail(text: str, limit: int = 1200) -> str:
    return hc.mask_secrets((text or "").strip())[-limit:]


def api_services_start() -> dict:
    """Bring up the postgres container via a single non-destructive compose call."""
    if not hc.docker_running():
        return {
            "ok": False,
            "message": "Docker isn't running. Start Docker Desktop (or the Docker service), then try again.",
            "output": "",
        }
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["docker", "compose", "up", "-d", "postgres"],
            cwd=str(hc.repo_root()),
            capture_output=True,
            timeout=180,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "docker compose timed out after 180s.", "output": ""}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "message": hc.mask_secrets(str(exc)), "output": ""}

    output = _mask_tail((proc.stdout or "") + (proc.stderr or ""))
    if proc.returncode != 0:
        return {
            "ok": False,
            "message": f"docker compose failed (exit {proc.returncode}).",
            "output": output,
        }
    return {"ok": True, "message": "PostgreSQL container is starting.", "output": output}


def api_launch() -> dict:
    """Start the full app via the launcher: install deps on first run, run
    migrations, start the backend (bound to all interfaces) and the frontend.
    Detached — progress lands in var/logs/setup.log; the Health step reflects
    readiness. This is the same proven path the desktop shortcut uses."""
    hc.ensure_dirs()
    hc.ensure_env_files()
    launch_script = hc.repo_root() / "installer" / "haven_launch.py"
    if not launch_script.exists():
        return {"ok": False, "message": f"Launcher not found at {launch_script}."}
    try:
        logf = open(hc.logs_dir() / "setup.log", "ab", buffering=0)  # noqa: SIM115 — handed to child
    except OSError as exc:
        return {"ok": False, "message": f"Could not open setup log: {hc.mask_secrets(str(exc))}"}
    kwargs: dict = {
        "stdout": logf, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL,
        "cwd": str(hc.repo_root()), "env": hc.enriched_env(),
    }
    if POSIX:
        kwargs["start_new_session"] = True
    else:  # Windows
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        subprocess.Popen([hc.venv_python() or sys.executable, str(launch_script)], **kwargs)  # noqa: S603
    except (OSError, ValueError) as exc:
        return {"ok": False, "message": hc.mask_secrets(str(exc))}
    return {
        "ok": True,
        "message": "Starting backend & frontend. First run installs dependencies "
                   "(this can take a few minutes) — watch the Health step below.",
    }


def api_health() -> dict:
    ports = _current_ports()
    backend_port = ports.get("backend") or hc.default_port("backend")
    frontend_port = ports.get("frontend") or hc.default_port("frontend")
    postgres_port = ports.get("postgres") or hc.default_port("postgres")

    backend = _http_ok(f"http://127.0.0.1:{backend_port}/api/v1/health", timeout=1.5)
    frontend = _http_ok(f"http://127.0.0.1:{frontend_port}", timeout=1.5)
    postgres = hc.port_in_use(int(postgres_port)) if postgres_port else False
    return {"backend": backend, "frontend": frontend, "postgres": postgres}


def api_shortcut() -> dict:
    frontend_port = _configured_or_default_port("frontend") or hc.default_port("frontend")
    app_url = f"http://localhost:{frontend_port}"
    return create_desktop_shortcut(app_url)


# --------------------------------------------------------------------------- #
# Page rendering (token injection)
# --------------------------------------------------------------------------- #

_TOKEN_PLACEHOLDER = "__HAVEN_SETUP_TOKEN__"


def _render_index() -> bytes:
    path = hc.repo_root() / "installer" / "web" / "index.html"
    html = path.read_text(encoding="utf-8")
    html = html.replace(_TOKEN_PLACEHOLDER, SETUP_TOKEN)
    return html.encode("utf-8")


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #


class _Handler(BaseHTTPRequestHandler):
    server_version = "HavenSetup/1.0"

    def log_message(self, *args):  # silence default logging
        pass

    # -- response helpers -------------------------------------------------- #

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-Setup-Token", ""), SETUP_TOKEN)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, UnicodeDecodeError):
            return {}

    # -- routing ----------------------------------------------------------- #

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if path == "/" or path == "/index.html":
                return self._send_html(200, _render_index())

            if path.startswith("/api/"):
                if not self._authed():
                    return self._send_json(403, {"ok": False, "message": "Forbidden — missing or bad setup token."})
                if path == "/api/detect":
                    return self._send_json(200, api_detect())
                if path == "/api/health":
                    return self._send_json(200, api_health())
                return self._send_json(404, {"ok": False, "message": "Unknown endpoint."})

            return self._send_html(404, b"<h1>404</h1>")
        except Exception as exc:  # noqa: BLE001
            return self._send_json(500, {"ok": False, "message": hc.mask_secrets(str(exc))})

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if not path.startswith("/api/"):
                return self._send_json(404, {"ok": False, "message": "Unknown endpoint."})
            if not self._authed():
                return self._send_json(403, {"ok": False, "message": "Forbidden — missing or bad setup token."})

            body = self._read_body()
            if path == "/api/ports/suggest":
                return self._send_json(200, api_ports_suggest(body))
            if path == "/api/env/apply":
                return self._send_json(200, api_env_apply(body))
            if path == "/api/agent/start":
                return self._send_json(200, api_agent_start())
            if path == "/api/services/start":
                return self._send_json(200, api_services_start())
            if path == "/api/launch":
                return self._send_json(200, api_launch())
            if path == "/api/shortcut":
                return self._send_json(200, api_shortcut())
            return self._send_json(404, {"ok": False, "message": "Unknown endpoint."})
        except Exception as exc:  # noqa: BLE001
            return self._send_json(500, {"ok": False, "message": hc.mask_secrets(str(exc))})


# --------------------------------------------------------------------------- #
# Server bootstrap
# --------------------------------------------------------------------------- #


def _choose_port() -> int:
    raw = os.environ.get("HAVEN_SETUP_PORT", "7000")
    try:
        port = int(raw)
    except (TypeError, ValueError):
        port = 7000
    if not hc.is_valid_port(port) or hc.port_in_use(port):
        free = hc.suggest_free_port(port if hc.is_valid_port(port) else 7000)
        if free is not None:
            port = free
    return port


def serve() -> None:
    global SETUP_TOKEN
    SETUP_TOKEN = secrets.token_urlsafe(32)
    hc.ensure_dirs()

    port = _choose_port()
    url = f"http://{SETUP_HOST}:{port}/"

    httpd = ThreadingHTTPServer((SETUP_HOST, port), _Handler)
    print("Haven Setup wizard")
    print(f"  Open: {url}")
    print("  (localhost only; the page carries a one-time setup token)")
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001 — headless boxes have no browser
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nSetup wizard stopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve()
