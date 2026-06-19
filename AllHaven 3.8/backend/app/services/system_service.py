"""System Control service — an authenticated, allowlisted proxy to the local
Haven agent.

The backend NEVER runs shell commands or Docker itself. It:
    * validates the service name + action against fixed allowlists (defense in
      depth — the agent validates too),
    * forwards the request to the localhost-only Haven agent using the shared
      on-disk token, and
    * falls back to a READ-ONLY, port-based status when the agent isn't running,
      so the panel still shows real state but offers no controls.

Port edits are written through ``env_file_service.sync_env`` (atomic write +
timestamped backup + 0600). Secrets are masked in any text returned to a client.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ValidationAppError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_AGENT_HOST = "127.0.0.1"

# --- Allowlists (mirror the agent; defense in depth) ----------------------- #
ALLOWED_ACTIONS = {"start", "stop", "restart"}  # "logs"/"status" have their own endpoints

SERVICES: dict[str, dict] = {
    "backend": {"label": "Backend API", "kind": "host", "port_env": "BACKEND_PORT", "default": 8000},
    "frontend": {"label": "Frontend", "kind": "host", "port_env": "FRONTEND_PORT", "default": 3000},
    "postgres": {"label": "PostgreSQL", "kind": "docker", "port_env": "POSTGRES_PORT", "default": 5432},
    "redis": {"label": "Redis", "kind": "docker", "port_env": "REDIS_PORT", "default": 6379, "optional": True},
    "n8n": {"label": "n8n", "kind": "docker", "port_env": "N8N_PORT", "default": 5678, "optional": True},
    "ollama": {"label": "Ollama", "kind": "docker", "port_env": "OLLAMA_PORT", "default": 11434,
               "optional": True, "host_daemon": True},
}

# Ports the UI may edit (always-present services + any optional one already set).
_EDITABLE_BASE = ("frontend", "backend", "postgres")
_EDITABLE_OPTIONAL = ("redis", "n8n")


# --- secret masking (mirror of the agent's, kept local to avoid cross-imports) #
_MASK_KEY = re.compile(
    r"(?im)^(\s*[A-Za-z0-9_]*"
    r"(?:SECRET|PASSWORD|PASSWD|TOKEN|API[_-]?KEY|_KEY|ENCRYPTION_KEY|CLIENT_SECRET)"
    r"[A-Za-z0-9_]*\s*[=:]\s*)(\S.*)$"
)
_MASK_URL = re.compile(r"(://[^:/\s]+:)([^@/\s]+)(@)")
_MASK_BEARER = re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._\-]+)")


def mask_secrets(text: str) -> str:
    if not text:
        return text
    text = _MASK_KEY.sub(lambda m: f"{m.group(1)}***", text)
    text = _MASK_URL.sub(lambda m: f"{m.group(1)}***{m.group(3)}", text)
    text = _MASK_BEARER.sub(lambda m: f"{m.group(1)}***", text)
    return text


# --- helpers --------------------------------------------------------------- #


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def control_enabled() -> bool:
    """Service control is allowed only when explicitly enabled AND in local mode."""
    return bool(settings.SYSTEM_CONTROL_ENABLED and settings.is_local_env)


def _agent_base() -> str:
    return f"http://{_AGENT_HOST}:{int(settings.HAVEN_AGENT_PORT)}"


def _token() -> str | None:
    p = _REPO_ROOT / "var" / "agent" / "token"
    try:
        return p.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _agent(method: str, path: str, payload: dict | None = None, timeout: float = 130.0):
    """Call the localhost agent. URL is fixed (localhost + configured port) — no
    user input enters the host/port, so this is not an SSRF vector."""
    headers = {"Accept": "application/json"}
    token = _token()
    if token:
        headers["X-Haven-Token"] = token
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{_agent_base()}{path}", data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed localhost URL)
        body = resp.read().decode("utf-8") or "{}"
        return resp.status, json.loads(body)


def _read_env() -> dict[str, str]:
    path = Path(settings.env_file_path)
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def _port_for(name: str, env: dict | None = None) -> int | None:
    env = env if env is not None else _read_env()
    spec = SERVICES[name]
    raw = env.get(spec["port_env"])
    if raw and raw.isdigit() and 1 <= int(raw) <= 65535:
        return int(raw)
    return spec["default"]


def _port_open(port: int | None) -> bool:
    if not port:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((_AGENT_HOST, int(port))) == 0


def _valid_port(value: object) -> bool:
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return 1 <= n <= 65535


# Ports config writes its OWN small fixed key set (separate from the integration
# web-sync allowlist, which intentionally excludes DATABASE_URL). DATABASE_URL is
# re-derived here only when the Postgres port changes, so the backend keeps
# connecting afterwards.
_PORT_ENV_WRITABLE = {"FRONTEND_PORT", "BACKEND_PORT", "POSTGRES_PORT", "REDIS_PORT", "N8N_PORT", "DATABASE_URL"}


def _write_env_keys(updates: dict[str, str]) -> dict:
    """Atomically write a small fixed set of keys to .env (backup + 0600).

    Only keys in ``_PORT_ENV_WRITABLE`` are ever written; every other line in the
    file (comments, secrets, other config) is preserved verbatim.
    """
    allowed = {k: str(v) for k, v in updates.items() if k in _PORT_ENV_WRITABLE}
    if not allowed:
        return {"backup": None, "keys": []}
    path = Path(settings.env_file_path)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out: list[str] = []
    seen: set[str] = set()
    for line in existing:
        s = line.strip()
        if s and not s.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in allowed:
                out.append(f"{key}={allowed[key]}")
                seen.add(key)
                continue
        out.append(line)
    for key, value in allowed.items():
        if key not in seen:
            out.append(f"{key}={value}")

    backup = None
    if path.exists():
        bpath = f"{path}.bak.{int(time.time())}"
        shutil.copy2(path, bpath)
        backup = os.path.basename(bpath)
    tmp = path.with_name(f"{path.name}.tmp.{uuid.uuid4().hex}")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return {"backup": backup, "keys": sorted(allowed)}


# --- status ---------------------------------------------------------------- #


def get_status() -> dict:
    enabled = control_enabled()
    try:
        code, body = _agent("GET", "/status", timeout=8.0)
        if code == 200 and isinstance(body, dict) and "services" in body:
            body["control_enabled"] = enabled
            body.setdefault("agent", {"running": True, "message": ""})
            return body
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        pass
    return _fallback_status(enabled)


def _fallback_status(enabled: bool) -> dict:
    env = _read_env()
    services = []
    for name, spec in SERVICES.items():
        port = _port_for(name, env)
        running = _port_open(port)
        if spec.get("optional") and not running:
            continue  # hide optional services that aren't up
        services.append({
            "name": name,
            "label": spec["label"],
            "kind": spec["kind"],
            "status": "running" if running else "stopped",
            "port": port,
            "controllable": False,
            "actions": [],
            "message": "Start Haven via the desktop launcher to enable controls.",
            "last_checked": _now(),
        })
    return {
        "agent": {
            "running": False,
            "message": "Haven Agent is not running. Start Haven via the desktop launcher "
                       "(or the START_HAVEN_* file) to enable Start/Stop/Restart and logs. "
                       "Status below is read-only.",
        },
        "control_enabled": enabled,
        "services": services,
    }


def _one_status(name: str) -> dict:
    spec = SERVICES[name]
    port = _port_for(name)
    return {
        "name": name, "label": spec["label"], "kind": spec["kind"],
        "status": "running" if _port_open(port) else "stopped",
        "port": port, "controllable": False, "actions": [],
        "message": "", "last_checked": _now(),
    }


# --- actions --------------------------------------------------------------- #


def do_action(name: str, action: str) -> dict:
    if name not in SERVICES:
        raise ValidationAppError(f"Unknown service '{name}'.")
    if action not in ALLOWED_ACTIONS:
        raise ValidationAppError(f"Action '{action}' is not allowed.")
    if not control_enabled():
        raise ValidationAppError("System Control is disabled on this deployment.")
    try:
        code, body = _agent("POST", f"/service/{name}/{action}")
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        raise ValidationAppError(
            "Haven Agent is not running. Start Haven via the desktop launcher to control services."
        )
    if not isinstance(body, dict) or not body.get("ok", code == 200):
        msg = body.get("message", "Action failed.") if isinstance(body, dict) else "Action failed."
        raise ValidationAppError(mask_secrets(str(msg)))
    return body.get("service") or _one_status(name)


def get_logs(name: str, lines: int = 300) -> dict:
    if name not in SERVICES:
        raise ValidationAppError(f"Unknown service '{name}'.")
    if not control_enabled():
        raise ValidationAppError("System Control is disabled on this deployment.")
    lines = max(1, min(int(lines), 1000))
    try:
        _, body = _agent("GET", f"/logs/{name}?lines={lines}", timeout=30.0)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        raise ValidationAppError(
            "Haven Agent is not running. Logs are available once Haven is started via the launcher."
        )
    if isinstance(body, dict) and body.get("content"):
        body["content"] = mask_secrets(body["content"])  # defense in depth
    return body


# --- ports ----------------------------------------------------------------- #


def get_ports() -> dict:
    env = _read_env()
    ports: dict[str, int] = {}
    defaults: dict[str, int] = {}
    for name in _EDITABLE_BASE:
        ports[name] = _port_for(name, env)
        defaults[name] = SERVICES[name]["default"]
    for name in _EDITABLE_OPTIONAL:
        if SERVICES[name]["port_env"] in env:
            ports[name] = _port_for(name, env)
            defaults[name] = SERVICES[name]["default"]
    return {"ports": ports, "defaults": defaults, "editable": control_enabled()}


def save_ports(updates: dict, restart: bool = False) -> dict:
    if not control_enabled():
        raise ValidationAppError("System Control is disabled on this deployment.")
    if not isinstance(updates, dict) or not updates:
        raise ValidationAppError("No ports provided.")

    clean: dict[str, int] = {}
    seen: dict[int, str] = {}
    for name, value in updates.items():
        if name not in SERVICES:
            raise ValidationAppError(f"Unknown service '{name}'.")
        if not _valid_port(value):
            raise ValidationAppError(f"{SERVICES[name]['label']}: port must be a whole number 1–65535.")
        n = int(value)
        if n in seen:
            raise ValidationAppError(f"Duplicate port {n}: {SERVICES[name]['label']} and {seen[n]}.")
        seen[n] = SERVICES[name]["label"]
        clean[name] = n

    current = get_ports()["ports"]
    env = _read_env()
    for name, n in clean.items():
        if current.get(name) != n and _port_open(n):
            raise ValidationAppError(
                f"Port {n} is already in use — choose another for {SERVICES[name]['label']}."
            )

    env_updates = {SERVICES[name]["port_env"]: str(n) for name, n in clean.items()}
    if "postgres" in clean:
        user = env.get("POSTGRES_USER", "allhaven")
        pw = env.get("POSTGRES_PASSWORD", "allhaven")
        db = env.get("POSTGRES_DB", "allhaven")
        host = env.get("POSTGRES_HOST", "localhost")
        env_updates["DATABASE_URL"] = (
            f"postgresql+psycopg://{user}:{pw}@{host}:{clean['postgres']}/{db}"
        )

    try:
        _write_env_keys(env_updates)
    except OSError as exc:
        raise ValidationAppError(f"Could not write .env: {exc}")

    applied = False
    notes: list[str] = []
    if restart:
        for name in clean:
            try:
                do_action(name, "restart")
                applied = True
                notes.append(f"{SERVICES[name]['label']} restarting")
            except ValidationAppError as exc:
                notes.append(f"{SERVICES[name]['label']}: {exc.message if hasattr(exc, 'message') else exc}")

    if restart:
        message = "Ports saved. " + ("; ".join(notes) if notes else "")
        if not applied:
            message += " (Could not restart automatically — restart Haven from the launcher to apply.)"
    else:
        message = "Ports saved. Port changes require a service restart to take effect."

    return {
        "ports": {**current, **clean},
        "restart_required": True,
        "applied": applied,
        "message": message,
    }
