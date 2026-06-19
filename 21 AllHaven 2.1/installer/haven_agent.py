"""Haven control agent — a tiny, localhost-only, token-gated process supervisor.

The agent is the ONLY place privileged operations happen. It is started by the
launcher / setup wizard and keeps running so the in-app "System Control" panel
(via the authenticated backend) can Start/Stop/Restart/inspect services.

Security model (all enforced here):
    * Binds 127.0.0.1 ONLY — never reachable off the machine.
    * Every request must carry ``X-Haven-Token`` equal to the on-disk token
      (``var/agent/token``, 0600). Constant-time compared.
    * Service names and actions are validated against fixed allowlists in
      ``haven_common``. Unknown names/actions are rejected with 400.
    * No shell, ever. Host services use fixed argv templates; Docker uses the
      non-destructive ``compose_argv`` builder (no down/rm/volume).
    * Log output is passed through ``mask_secrets`` before returning.

Stdlib only. Run with:  python installer/haven_agent.py
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import haven_common as hc  # noqa: E402

POSIX = os.name == "posix"
_COMPOSE_TIMEOUT = 120


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Low-level process helpers
# --------------------------------------------------------------------------- #


def _pid_file(name: str) -> Path:
    return hc.agent_dir() / f"{name}.pid"


def _log_file(name: str) -> Path:
    return hc.logs_dir() / f"{name}.log"


def _read_pid(name: str) -> int | None:
    p = _pid_file(name)
    if not p.exists():
        return None
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    except PermissionError:
        return True
    return True


def _configured_port(name: str) -> int | None:
    env = hc.read_env()
    key = hc.port_env_key(name)
    if key and key in env and hc.is_valid_port(env[key]):
        return int(env[key])
    return hc.default_port(name)


# --------------------------------------------------------------------------- #
# Host service control (backend / frontend)
# --------------------------------------------------------------------------- #


def _spawn(name: str, argv: list[str], cwd: Path) -> None:
    hc.ensure_dirs()
    logf = open(_log_file(name), "ab", buffering=0)  # noqa: SIM115 (kept open for child)
    kwargs: dict = {"cwd": str(cwd), "stdout": logf, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
    if POSIX:
        kwargs["start_new_session"] = True  # detach: survives agent, own process group
    else:  # Windows
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(argv, **kwargs)  # noqa: S603 (argv list, no shell)
    _pid_file(name).write_text(str(proc.pid), encoding="utf-8")


def _host_start(name: str) -> dict:
    if _host_is_running(name):
        return {"ok": True, "message": f"{name} already running."}
    port = _configured_port(name) or hc.default_port(name)
    if name == "backend":
        argv = hc.backend_command(hc.venv_python(), port)
        cwd = hc.repo_root() / "backend"
    elif name == "frontend":
        argv = hc.frontend_command(port)
        cwd = hc.repo_root() / "frontend"
    else:
        return {"ok": False, "message": f"Unknown host service '{name}'."}
    try:
        _spawn(name, argv, cwd)
    except (OSError, ValueError) as exc:
        return {"ok": False, "message": f"Could not start {name}: {hc.mask_secrets(str(exc))}"}
    return {"ok": True, "message": f"Starting {name} on port {port}."}


def _host_stop(name: str) -> dict:
    pid = _read_pid(name)
    if not _pid_alive(pid):
        _pid_file(name).unlink(missing_ok=True)
        return {"ok": True, "message": f"{name} is not running."}
    try:
        if POSIX:
            os.killpg(os.getpgid(pid), signal.SIGTERM)  # type: ignore[arg-type]
        else:
            os.kill(pid, signal.SIGTERM)  # type: ignore[arg-type]
    except (OSError, ProcessLookupError):
        pass
    for _ in range(20):
        if not _pid_alive(pid):
            break
        time.sleep(0.25)
    if _pid_alive(pid):
        try:
            if POSIX:
                os.killpg(os.getpgid(pid), signal.SIGKILL)  # type: ignore[arg-type]
            else:
                os.kill(pid, signal.SIGTERM)  # type: ignore[arg-type]
        except (OSError, ProcessLookupError):
            pass
    _pid_file(name).unlink(missing_ok=True)
    return {"ok": True, "message": f"Stopped {name}."}


def _host_is_running(name: str) -> bool:
    port = _configured_port(name)
    if port and hc.port_in_use(port):
        return True
    return _pid_alive(_read_pid(name))


def _host_status(name: str) -> str:
    return "running" if _host_is_running(name) else "stopped"


# --------------------------------------------------------------------------- #
# Docker service control
# --------------------------------------------------------------------------- #


def _docker_ok() -> bool:
    if not hc.which("docker"):
        return False
    try:
        r = subprocess.run(  # noqa: S603
            ["docker", "info"], cwd=str(hc.repo_root()),
            capture_output=True, timeout=10, text=True,
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _run_compose(argv: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(  # noqa: S603 (argv from allowlist builder, no shell)
            argv, cwd=str(hc.repo_root()), capture_output=True,
            timeout=_COMPOSE_TIMEOUT, text=True,
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "docker compose timed out."
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def _docker_action(name: str, action: str) -> dict:
    spec = hc.DOCKER_SERVICES.get(name, {})
    compose = spec.get("compose")
    if spec.get("host_daemon"):
        return {"ok": False, "message": f"{spec.get('label', name)} runs on the host and is not controlled by Haven."}
    if not compose:
        return {"ok": False, "message": f"{name} is not a compose-managed service."}
    if not _docker_ok():
        return {"ok": False, "message": "Docker is not available. Start Docker Desktop / the Docker service."}
    argv = hc.compose_argv(action, compose)
    if argv is None:
        return {"ok": False, "message": f"Action '{action}' is not allowed."}
    rc, out = _run_compose(argv)
    if rc != 0:
        return {"ok": False, "message": hc.mask_secrets(out.strip()[-400:] or f"docker compose failed (rc={rc}).")}
    return {"ok": True, "message": f"{action} {name}: ok."}


def _docker_status(name: str) -> str:
    spec = hc.DOCKER_SERVICES.get(name, {})
    if spec.get("host_daemon"):
        port = _configured_port(name)
        return "running" if (port and hc.port_in_use(port)) else "stopped"
    compose = spec.get("compose")
    if not compose:
        return "unavailable"
    if not _docker_ok():
        return "unavailable"
    argv = hc.compose_argv("status", compose)
    rc, out = _run_compose([*argv, "--format", "json"]) if argv else (1, "")
    if rc == 0 and out.strip():
        low = out.lower()
        if '"state":"running"' in low.replace(" ", "") or '"running"' in low or "running" in low:
            return "running"
    port = _configured_port(name)
    if port and hc.port_in_use(port):
        return "running"
    return "stopped"


# --------------------------------------------------------------------------- #
# Logs
# --------------------------------------------------------------------------- #


def _tail_text(text: str, lines: int) -> tuple[str, bool]:
    split = text.splitlines()
    if len(split) <= lines:
        return "\n".join(split), False
    return "\n".join(split[-lines:]), True


def _read_logs(name: str, lines: int) -> dict:
    lines = max(1, min(int(lines), 1000))
    kind = hc.service_kind(name)
    if kind == "host":
        f = _log_file(name)
        if not f.exists():
            return {"name": name, "content": "", "truncated": False,
                    "message": "No log file yet — start the service first."}
        try:
            raw = f.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"name": name, "content": "", "truncated": False, "message": str(exc)}
        content, trunc = _tail_text(raw, lines)
        return {"name": name, "content": hc.mask_secrets(content), "truncated": trunc, "message": ""}
    # docker
    spec = hc.DOCKER_SERVICES.get(name, {})
    compose = spec.get("compose")
    if not compose or spec.get("host_daemon"):
        return {"name": name, "content": "", "truncated": False,
                "message": "Logs are not available for this service."}
    if not _docker_ok():
        return {"name": name, "content": "", "truncated": False, "message": "Docker is not available."}
    argv = hc.compose_argv("logs", compose, lines=lines)
    rc, out = _run_compose(argv) if argv else (1, "")
    content, trunc = _tail_text(out, lines)
    return {"name": name, "content": hc.mask_secrets(content), "truncated": trunc,
            "message": "" if rc == 0 else f"docker compose logs rc={rc}"}


# --------------------------------------------------------------------------- #
# Status snapshot + actions
# --------------------------------------------------------------------------- #


def _compose_has(service: str) -> bool:
    """Best-effort: is the service defined/enabled in docker-compose.yml?"""
    f = hc.repo_root() / "docker-compose.yml"
    if not f.exists():
        return False
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return False
    # Match an uncommented "  <service>:" service key.
    import re

    return re.search(rf"(?m)^\s{{2}}{re.escape(service)}\s*:", text) is not None


def _service_present(name: str) -> bool:
    if name in hc.HOST_SERVICES:
        return True
    spec = hc.DOCKER_SERVICES.get(name, {})
    if spec.get("host_daemon"):  # ollama: present if a port is configured/responding
        port = _configured_port(name)
        return bool(port and hc.port_in_use(port))
    compose = spec.get("compose")
    if not spec.get("optional"):
        return True  # postgres always present
    return _compose_has(compose) if compose else False


def _status_for(name: str) -> dict:
    spec = hc.ALL_SERVICES[name]
    kind = spec["kind"]
    present = _service_present(name)
    if kind == "host":
        state = _host_status(name)
        actions = ["start", "stop", "restart", "logs"]
    else:
        state = _docker_status(name) if present else "unavailable"
        if spec.get("host_daemon"):
            actions = []  # ollama: status only (never touch the user's host daemon)
        elif present:
            actions = ["start", "stop", "restart", "logs"]
        else:
            actions = []
    return {
        "name": name,
        "label": spec["label"],
        "kind": kind,
        "status": state,
        "port": _configured_port(name),
        "controllable": bool(actions) and state != "unavailable",
        "actions": actions,
        "message": "" if present else "Optional service not enabled.",
        "last_checked": _now(),
    }


def build_status() -> dict:
    services = []
    for name in hc.ALL_SERVICES:
        if name in hc.DOCKER_SERVICES and hc.DOCKER_SERVICES[name].get("optional"):
            if not _service_present(name):
                continue  # hide optional services that aren't enabled
        services.append(_status_for(name))
    return {"agent": {"running": True, "message": ""}, "control_enabled": True, "services": services}


def perform_action(name: str, action: str) -> dict:
    if not hc.is_valid_service(name):
        return {"ok": False, "code": 400, "message": f"Unknown service '{name}'."}
    if not hc.is_valid_action(action) or action == "status":
        return {"ok": False, "code": 400, "message": f"Unknown action '{action}'."}
    kind = hc.service_kind(name)
    if kind == "host":
        if action == "start":
            res = _host_start(name)
        elif action == "stop":
            res = _host_stop(name)
        elif action == "restart":
            _host_stop(name)
            time.sleep(0.8)
            res = _host_start(name)
        else:
            res = {"ok": False, "message": "Unsupported."}
    else:
        if action == "restart":
            res = _docker_action(name, "restart")
        else:
            res = _docker_action(name, action)
    res.setdefault("code", 200 if res.get("ok") else 409)
    res["service"] = _status_for(name)
    return res


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #


class _Handler(BaseHTTPRequestHandler):
    server_version = "HavenAgent/1.0"

    def log_message(self, *args):  # silence default logging
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        return hc.tokens_match(self.headers.get("X-Haven-Token"))

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/ping":
            return self._send(200, {"ok": True, "agent": "haven"})
        if not self._authed():
            return self._send(401, {"ok": False, "message": "Unauthorized."})
        if path == "/status":
            return self._send(200, build_status())
        if path.startswith("/logs/"):
            name = path[len("/logs/"):]
            if not hc.is_valid_service(name):
                return self._send(400, {"ok": False, "message": "Unknown service."})
            qs = parse_qs(parsed.query)
            try:
                lines = int(qs.get("lines", ["300"])[0])
            except (ValueError, IndexError):
                lines = 300
            return self._send(200, _read_logs(name, lines))
        return self._send(404, {"ok": False, "message": "Not found."})

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if not self._authed():
            return self._send(401, {"ok": False, "message": "Unauthorized."})
        if path == "/open":
            import webbrowser

            port = _configured_port("frontend") or 3000
            webbrowser.open(f"http://localhost:{port}")
            return self._send(200, {"ok": True, "message": "Opening Haven…"})
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "service":
            _, name, action = parts
            result = perform_action(name, action)
            return self._send(result.get("code", 200), result)
        return self._send(404, {"ok": False, "message": "Not found."})


def serve() -> None:
    hc.ensure_dirs()
    hc.ensure_token()
    _pid_file("agent").write_text(str(os.getpid()), encoding="utf-8")
    httpd = ThreadingHTTPServer((hc.AGENT_HOST, hc.agent_port()), _Handler)
    print(f"Haven agent listening on {hc.agent_base_url()} (localhost only)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve()
