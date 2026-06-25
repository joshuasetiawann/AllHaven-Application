"""Haven installer/agent shared helpers — Python standard library ONLY.

This module is imported by both the first-run setup wizard (``haven_setup.py``)
and the long-running control agent (``haven_agent.py``). It deliberately has **no
third-party dependencies** so it runs on a fresh machine before anything is
installed.

Everything here is pure/side-effect-light and unit-tested (see
``installer/tests/``). Process spawning and HTTP serving live in the agent/setup
modules, not here, so this stays safe to import and easy to test.

Security notes:
    * Service names and actions are validated against fixed allowlists.
    * Docker is only ever driven through a small set of NON-destructive compose
      subcommands built as argv lists (never a shell string). ``down`` and any
      volume removal are intentionally impossible to express here.
    * ``mask_secrets`` scrubs key-like values from any text before it is shown.
    * ``apply_env_updates`` backs up ``.env`` and only rewrites the keys asked
      for, preserving every other line (including existing secrets) verbatim.
"""

from __future__ import annotations

import os
import platform
import re
import secrets
import socket
import stat
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #


def repo_root() -> Path:
    """Repo root = the directory that contains this ``installer`` package."""
    return Path(__file__).resolve().parents[1]


def var_dir() -> Path:
    return repo_root() / "var"


def logs_dir() -> Path:
    return var_dir() / "logs"


def agent_dir() -> Path:
    return var_dir() / "agent"


def env_path() -> Path:
    return repo_root() / ".env"


def env_example_path() -> Path:
    return repo_root() / ".env.example"


def ensure_dirs() -> None:
    for d in (var_dir(), logs_dir(), agent_dir()):
        d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Agent token (localhost auth)
# --------------------------------------------------------------------------- #

_TOKEN_FILE = "token"


def token_path() -> Path:
    return agent_dir() / _TOKEN_FILE


def ensure_token() -> str:
    """Return the agent token, creating a fresh 0600 token file if needed."""
    ensure_dirs()
    p = token_path()
    if p.exists():
        existing = p.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    tok = secrets.token_urlsafe(32)
    p.write_text(tok, encoding="utf-8")
    try:
        p.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600 — owner only
    except OSError:
        pass  # best effort on platforms without POSIX perms (Windows)
    return tok


def read_token() -> str | None:
    p = token_path()
    if not p.exists():
        return None
    val = p.read_text(encoding="utf-8").strip()
    return val or None


def tokens_match(provided: str | None) -> bool:
    """Constant-time compare against the on-disk token."""
    expected = read_token()
    if not expected or not provided:
        return False
    return secrets.compare_digest(provided, expected)


# --------------------------------------------------------------------------- #
# Agent network location
# --------------------------------------------------------------------------- #

AGENT_HOST = "127.0.0.1"  # localhost ONLY — never bind 0.0.0.0


def agent_port() -> int:
    raw = os.environ.get("HAVEN_AGENT_PORT", "8765")
    try:
        p = int(raw)
        return p if is_valid_port(p) else 8765
    except (TypeError, ValueError):
        return 8765


def agent_base_url() -> str:
    return f"http://{AGENT_HOST}:{agent_port()}"


# --------------------------------------------------------------------------- #
# Ports
# --------------------------------------------------------------------------- #

MIN_PORT = 1
MAX_PORT = 65535


def is_valid_port(value: object) -> bool:
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return MIN_PORT <= n <= MAX_PORT


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """True if something is already listening on host:port."""
    if not is_valid_port(port):
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, int(port))) == 0


def suggest_free_port(start: int, taken: set[int] | None = None, limit: int = 200) -> int | None:
    """First valid, free port at/after ``start`` not already in ``taken``."""
    taken = taken or set()
    if not is_valid_port(start):
        start = 1024
    for candidate in range(int(start), min(int(start) + limit, MAX_PORT + 1)):
        if candidate in taken:
            continue
        if not port_in_use(candidate):
            return candidate
    return None


def validate_ports(ports: dict[str, int]) -> dict[str, str]:
    """Return {key: error} for any invalid / duplicate / in-use port. Empty = OK."""
    errors: dict[str, str] = {}
    seen: dict[int, str] = {}
    for key, value in ports.items():
        if not is_valid_port(value):
            errors[key] = "Must be a whole number between 1 and 65535."
            continue
        n = int(value)
        if n in seen:
            errors[key] = f"Duplicate port — also used by '{seen[n]}'."
            continue
        seen[n] = key
    return errors


# --------------------------------------------------------------------------- #
# .env reading / safe updating
# --------------------------------------------------------------------------- #

_ENV_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def read_env(path: Path | None = None) -> dict[str, str]:
    """Parse KEY=VALUE pairs (ignoring comments/blanks). Order not preserved."""
    path = path or env_path()
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _ENV_LINE.match(line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def apply_env_updates(
    updates: dict[str, str],
    path: Path | None = None,
    example_path: Path | None = None,
    backup: bool = True,
) -> dict:
    """Safely update ``.env``.

    * Creates ``.env`` from ``.env.example`` (or empty) if missing.
    * Backs the existing file up to ``.env.bak-<ts>`` first.
    * Rewrites ONLY the keys in ``updates`` (appending any new ones); every other
      line — including existing secrets and comments — is preserved verbatim.
    * Never logs or returns any value.

    Returns ``{"backup": <path|None>, "updated_keys": [...], "created": bool}``.
    """
    path = path or env_path()
    example_path = example_path or env_example_path()
    created = False
    backup_path: str | None = None

    if not path.exists():
        if example_path.exists():
            path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            path.write_text("", encoding="utf-8")
        created = True

    if backup and not created and path.exists():
        # Use the ".env.bak.<ts>" form so it matches the ".env.bak.*" gitignore rule.
        bpath = path.with_name(f"{path.name}.bak.{_timestamp()}")
        bpath.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        backup_path = str(bpath)

    lines = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)
    out: list[str] = []
    for line in lines:
        m = _ENV_LINE.match(line)
        if m and m.group(1) in remaining:
            key = m.group(1)
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    for key, value in remaining.items():  # keys not already present
        out.append(f"{key}={value}")

    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return {"backup": backup_path, "updated_keys": sorted(updates.keys()), "created": created}


# --------------------------------------------------------------------------- #
# Secret masking
# --------------------------------------------------------------------------- #

_SECRET_KEY_RE = re.compile(
    r"(?im)^(\s*[A-Za-z0-9_]*"
    r"(?:SECRET|PASSWORD|PASSWD|TOKEN|API[_-]?KEY|_KEY|ENCRYPTION_KEY|CLIENT_SECRET|ACCESS_KEY)"
    r"[A-Za-z0-9_]*\s*[=:]\s*)(\S.*)$"
)
_URL_CRED_RE = re.compile(r"(://[^:/\s]+:)([^@/\s]+)(@)")
_BEARER_RE = re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._\-]+)")
_INLINE_KV_RE = re.compile(
    r"(?i)\b([A-Za-z0-9_]*(?:secret|password|token|api[_-]?key)[A-Za-z0-9_]*)"
    r'(["\']?\s*[=:]\s*["\']?)([^\s"\',]+)'
)

_MASK = "***"


def mask_secrets(text: str) -> str:
    """Scrub secret-like values from arbitrary text (logs, errors, env dumps)."""
    if not text:
        return text
    text = _SECRET_KEY_RE.sub(lambda m: f"{m.group(1)}{_MASK}", text)
    text = _URL_CRED_RE.sub(lambda m: f"{m.group(1)}{_MASK}{m.group(3)}", text)
    text = _BEARER_RE.sub(lambda m: f"{m.group(1)}{_MASK}", text)
    text = _INLINE_KV_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{_MASK}", text)
    return text


# --------------------------------------------------------------------------- #
# OS / Docker detection
# --------------------------------------------------------------------------- #


def detect_os() -> str:
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        return "windows"
    if sysname == "darwin":
        return "macos"
    if sysname == "linux":
        return "linux"
    return "linux"


def which(cmd: str) -> str | None:
    from shutil import which as _which

    return _which(cmd)


def docker_installed() -> bool:
    return which("docker") is not None


def docker_running() -> bool:
    """True if the Docker daemon answers (``docker info`` succeeds)."""
    if not docker_installed():
        return False
    import subprocess

    try:
        # `docker info` can be heavy; a server-version query is a lighter daemon
        # round-trip, bounded by a short timeout so the check is quick and never
        # stalls (e.g. when Docker Desktop is still starting).
        r = subprocess.run(  # noqa: S603,S607
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True, timeout=4, text=True,
        )
        return r.returncode == 0 and bool((r.stdout or "").strip())
    except (OSError, subprocess.SubprocessError):
        return False


def compose_available() -> bool:
    if not docker_installed():
        return False
    import subprocess

    try:
        r = subprocess.run(["docker", "compose", "version"], capture_output=True, timeout=4, text=True)  # noqa: S603,S607
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def docker_install_url(os_name: str | None = None) -> str:
    os_name = os_name or detect_os()
    return {
        "windows": "https://docs.docker.com/desktop/install/windows-install/",
        "macos": "https://docs.docker.com/desktop/install/mac-install/",
        "linux": "https://docs.docker.com/engine/install/",
    }.get(os_name, "https://docs.docker.com/get-docker/")


# --------------------------------------------------------------------------- #
# Service registry + allowlists  (THE security boundary)
# --------------------------------------------------------------------------- #

# Fixed action allowlist. Nothing outside this set is ever executed.
ACTIONS = ("status", "start", "stop", "restart", "logs")

# Host process services (managed by the agent via tracked subprocesses).
HOST_SERVICES: dict[str, dict] = {
    "backend": {"label": "Backend API", "kind": "host", "port_env": "BACKEND_PORT", "default_port": 8000},
    "frontend": {"label": "Frontend", "kind": "host", "port_env": "FRONTEND_PORT", "default_port": 3000},
}

# Docker-compose-managed services. ``compose`` is the service name in
# docker-compose.yml; ``None`` means "not compose-managed" (host daemon).
DOCKER_SERVICES: dict[str, dict] = {
    "postgres": {"label": "PostgreSQL", "kind": "docker", "compose": "postgres",
                 "port_env": "POSTGRES_PORT", "default_port": 5432, "optional": False},
    "redis": {"label": "Redis", "kind": "docker", "compose": "redis",
              "port_env": "REDIS_PORT", "default_port": 6379, "optional": True},
    "n8n": {"label": "n8n", "kind": "docker", "compose": "n8n",
            "port_env": "N8N_PORT", "default_port": 5678, "optional": True},
    "ollama": {"label": "Ollama", "kind": "docker", "compose": None,
               "port_env": "OLLAMA_PORT", "default_port": 11434, "optional": True, "host_daemon": True},
}

ALL_SERVICES = {**HOST_SERVICES, **DOCKER_SERVICES}


def is_valid_service(name: str) -> bool:
    return name in ALL_SERVICES


def is_valid_action(action: str) -> bool:
    return action in ACTIONS


def service_kind(name: str) -> str | None:
    spec = ALL_SERVICES.get(name)
    return spec["kind"] if spec else None


def default_port(name: str) -> int | None:
    spec = ALL_SERVICES.get(name)
    return spec["default_port"] if spec else None


def port_env_key(name: str) -> str | None:
    spec = ALL_SERVICES.get(name)
    return spec["port_env"] if spec else None


# --------------------------------------------------------------------------- #
# Docker compose argv builder (NON-destructive only)
# --------------------------------------------------------------------------- #

# Only these compose subcommands can ever be produced. There is no code path
# that yields ``down``, ``rm``, ``kill``, or any ``volume`` operation.
_COMPOSE_ACTION_ARGS: dict[str, list[str]] = {
    "start": ["up", "-d"],
    "stop": ["stop"],
    "restart": ["restart"],
    "status": ["ps"],
    "logs": ["logs", "--no-color", "--tail", "{lines}"],
}


def compose_argv(action: str, compose_service: str, lines: int = 300) -> list[str] | None:
    """Build a safe ``docker compose ...`` argv list, or None if not allowed."""
    if action not in _COMPOSE_ACTION_ARGS or not compose_service:
        return None
    # compose service must be a known, simple identifier
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", compose_service):
        return None
    lines = max(1, min(int(lines), 2000))
    tail = [a.format(lines=lines) for a in _COMPOSE_ACTION_ARGS[action]]
    return ["docker", "compose", *tail, compose_service]


# --------------------------------------------------------------------------- #
# Host service start commands (argv templates — pure data, no spawning here)
# --------------------------------------------------------------------------- #


def backend_command(python_exe: str, port: int, host: str = "127.0.0.1") -> list[str]:
    return [python_exe, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(int(port))]


def frontend_command(port: int, host: str = "127.0.0.1", mode: str = "dev") -> list[str]:
    npm = "npm.cmd" if detect_os() == "windows" else "npm"
    if mode == "start":
        return [npm, "run", "start", "--", "-p", str(int(port)), "-H", host]
    return [npm, "run", "dev", "--", "-p", str(int(port)), "-H", host]


def venv_dir() -> Path:
    return repo_root() / "backend" / ".venv"


def venv_python() -> str:
    """Path to the backend venv's python, falling back to the current one."""
    root = repo_root()
    candidates = [
        root / "backend" / ".venv" / "bin" / "python",
        root / "backend" / ".venv" / "Scripts" / "python.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    import sys

    return sys.executable


def venv_python_path() -> Path:
    """The EXPECTED venv python path (no fallback). May not exist — use this when
    you need to know about the venv itself, not 'some' python to run."""
    d = venv_dir()
    return (d / "Scripts" / "python.exe") if detect_os() == "windows" else (d / "bin" / "python")


def venv_bin(name: str) -> Path:
    """Path to a console script inside the venv (e.g. ``alembic``, ``pip``)."""
    d = venv_dir()
    return (d / "Scripts" / f"{name}.exe") if detect_os() == "windows" else (d / "bin" / name)


def venv_alembic_argv(*args: str) -> list[str]:
    """argv to run Alembic THROUGH THE VENV.

    Prefer the venv console script (``.venv/bin/alembic``) — it is always correct
    for the installed Alembic version and never depends on a non-venv interpreter.
    This is the fix for ``python -m alembic`` failing with "No module named
    alembic.__main__" when an older/foreign Alembic (e.g. the system one, picked up
    after the venv fell back to ``sys.executable``) has no ``__main__`` module.
    """
    script = venv_bin("alembic")
    if script.exists():
        return [str(script), *args]
    # Last resort only if the console script is somehow absent: use the venv python
    # explicitly (never the system one) so we don't run a foreign Alembic.
    py = venv_python_path()
    return [str(py) if py.exists() else venv_python(), "-m", "alembic", *args]


def _run_rc(argv: list[str], timeout: float = 20.0) -> int:
    """Run argv quietly and return its exit code (127 if it can't be launched)."""
    import subprocess

    try:
        return subprocess.run(  # noqa: S603 (fixed argv, no shell)
            argv, capture_output=True, timeout=timeout
        ).returncode
    except FileNotFoundError:
        return 127
    except (OSError, subprocess.SubprocessError):
        return 1


def venv_interpreter_ok() -> bool:
    """True if the venv's python exists AND can actually execute.

    Catches a *dangling* interpreter — e.g. the base Python was upgraded/removed
    out from under the venv — which ``pip install`` cannot repair. (Missing
    dependencies are NOT a failure here; a fresh venv also has none.)
    """
    py = venv_python_path()
    if not py.exists():
        return False
    return _run_rc([str(py), "-c", "import sys"], timeout=15) == 0


def venv_deps_ok(probe: str = "fastapi") -> bool:
    """True if the venv can import a core backend dependency (deps installed and
    ABI-compatible). False on a fresh venv (needs ``pip install``) or a broken one."""
    py = venv_python_path()
    if not py.exists():
        return False
    return _run_rc([str(py), "-c", f"import {probe}"], timeout=30) == 0


def backend_venv_broken() -> bool:
    """A venv directory that exists but whose interpreter cannot run.

    Distinct from 'needs dependencies': this state requires a rebuild, not a
    ``pip install``. Based purely on EXECUTION — never on ``pyvenv.cfg`` metadata,
    which can be stale (e.g. recorded version differs from the resolved binary)
    yet still describe a perfectly working venv.
    """
    return venv_dir().exists() and not venv_interpreter_ok()


def quarantine_broken_venv() -> str | None:
    """Move a broken venv aside to ``.venv.broken.<timestamp>`` (NEVER delete).

    Returns the new directory name, or None if there was nothing to move / the
    rename failed. Renaming (not deleting) keeps any salvageable state for the user.
    """
    d = venv_dir()
    if not d.exists():
        return None
    target = d.with_name(f".venv.broken.{_timestamp()}")
    try:
        d.rename(target)
        return target.name
    except OSError:
        return None


def db_settings_are_default(env: dict | None = None) -> bool:
    """True when DATABASE_URL is unset/empty or equals the auto-generated local
    form, so changing the Postgres port is safe. A CUSTOM DATABASE_URL returns
    False and must be left untouched (never silently rewritten)."""
    env = env if env is not None else read_env()
    url = (env.get("DATABASE_URL") or "").strip()
    if not url:
        return True
    user = env.get("POSTGRES_USER", "allhaven")
    pw = env.get("POSTGRES_PASSWORD", "allhaven")
    host = env.get("POSTGRES_HOST", "localhost")
    db = env.get("POSTGRES_DB", "allhaven")
    port = env.get("POSTGRES_PORT", "5432")
    return url == f"postgresql+psycopg://{user}:{pw}@{host}:{port}/{db}"


# --------------------------------------------------------------------------- #
# Launch helpers (faithful to allhaven.sh, which is the proven manual flow)
# --------------------------------------------------------------------------- #

# Managed app services bind all interfaces (matching allhaven.sh) so the app is
# reachable at localhost AND on the LAN, and so a localhost->::1 (IPv6) lookup
# can't miss an IPv4-only bind. The AGENT itself stays 127.0.0.1-only.
APP_BIND_HOST = "0.0.0.0"


def enriched_env() -> dict:
    """``os.environ`` with PATH augmented for GUI launches.

    Double-clicked launchers often start with a minimal PATH, so node/npm/docker
    aren't found even though they work in a terminal. Prepend the backend venv bin
    and append the usual tool locations.
    """
    env = dict(os.environ)
    extra_back = [
        "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin",
        "/opt/homebrew/bin", "/opt/homebrew/sbin", "/snap/bin",
        str(Path.home() / ".local" / "bin"),
    ]
    venv_bin = repo_root() / "backend" / ".venv" / ("Scripts" if detect_os() == "windows" else "bin")
    parts = (env.get("PATH", "") or "").split(os.pathsep)
    parts = [p for p in parts if p]
    if venv_bin.exists() and str(venv_bin) not in parts:
        parts.insert(0, str(venv_bin))
    for p in extra_back:
        if p not in parts:
            parts.append(p)
    env["PATH"] = os.pathsep.join(parts)
    return env


def ensure_env_files() -> dict:
    """Keep the per-folder env files in sync with the repo-root ``.env``.

    * ``backend/.env`` is mirrored from the repo-root ``.env`` (rewritten whenever it
      differs) so running uvicorn from ``backend/`` always sees the same config.
      Because this runs on every start, a later root-``.env`` change (e.g. a port
      edit) propagates on the next launch — no staleness.
    * ``frontend/.env.local`` is created from its example if missing (Next.js reads
      it for the API base URL).

    Returns ``{"created": [...]}`` — file names only, never any values.
    """
    created: list[str] = []
    root = repo_root()
    root_env = root / ".env"
    backend_env = root / "backend" / ".env"
    if root_env.exists():
        try:
            content = root_env.read_text(encoding="utf-8")
            if (not backend_env.exists()) or backend_env.read_text(encoding="utf-8") != content:
                backend_env.write_text(content, encoding="utf-8")
                try:
                    backend_env.chmod(stat.S_IRUSR | stat.S_IWUSR)
                except OSError:
                    pass
                created.append("backend/.env")
        except OSError:
            pass
    fe_local = root / "frontend" / ".env.local"
    fe_example = root / "frontend" / ".env.local.example"
    if not fe_local.exists() and fe_example.exists():
        fe_local.write_text(fe_example.read_text(encoding="utf-8"), encoding="utf-8")
        created.append("frontend/.env.local")
    return {"created": created}


def ensure_dotenv() -> dict:
    """Create the repo-root ``.env`` from ``.env.example`` with fresh secrets if it
    doesn't exist yet (never overwrites an existing ``.env``). Then mirror it to
    ``backend/.env``. Returns ``{"created": bool}`` — never any secret values."""
    import re as _re
    import secrets as _secrets

    p = env_path()
    created = False
    if not p.exists():
        example = env_example_path()
        text = example.read_text(encoding="utf-8") if example.exists() else ""

        def _set(t: str, key: str, val: str) -> str:
            if _re.search(rf"(?m)^{key}=", t):
                return _re.sub(rf"(?m)^{key}=.*$", f"{key}={val}", t)
            sep = "" if (not t or t.endswith("\n")) else "\n"
            return f"{t}{sep}{key}={val}\n"

        text = _set(text, "SECRET_KEY", _secrets.token_urlsafe(48))
        text = _set(text, "SETTINGS_ENCRYPTION_KEY", _secrets.token_urlsafe(32))
        text = _set(text, "BACKEND_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        p.write_text(text, encoding="utf-8")
        try:
            p.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        created = True
    ensure_env_files()  # mirror to backend/.env (+ frontend/.env.local)
    return {"created": created}


def backend_setup_ok() -> bool:
    venv = repo_root() / "backend" / ".venv"
    return (venv / "bin" / "python").exists() or (venv / "Scripts" / "python.exe").exists()


def frontend_setup_ok() -> bool:
    return (repo_root() / "frontend" / "node_modules").is_dir()


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 60.0) -> bool:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_in_use(port, host):
            return True
        time.sleep(1.0)
    return False


def wait_for_http(url: str, timeout: float = 60.0) -> bool:
    """Poll ``url`` until it returns a real success (2xx), or time out.

    urllib raises ``HTTPError`` (an ``OSError``) on 4xx/5xx and follows 3xx, so by
    the time we read ``r.status`` it is already 2xx; the ``< 300`` bound keeps the
    success condition honest (e.g. Next's dev "missing required error components"
    placeholder is served as 404 → raises → we keep polling until the route's real
    200, never accepting the placeholder).
    """
    import time
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:  # noqa: S310 (localhost)
                if 200 <= r.status < 300:
                    return True
        except OSError:
            pass
        time.sleep(1.0)
    return False
