"""AllHaven for Windows — first-run setup wizard and everyday control panel.

One entry point, two faces: it runs the setup wizard when the machine isn't set up
yet, and the control panel afterwards. This is the script PyInstaller freezes into
``AllHaven-Setup.exe`` (see ``build_exe.py``), so it is **stdlib only** — no imports
from the repo, nothing to install first.

What setup does:
  1. Checks prerequisites (Docker Desktop, Docker Compose) and, with your consent,
     installs the missing ones through winget.
  2. Asks which host ports to publish on, flagging any that are already taken and
     offering the next free one.
  3. Asks how data is stored — local PostgreSQL, Supabase cloud, or both — and can
     create the Supabase project for you if you do not have one yet.
  4. Writes .env.prod with freshly generated secrets (never overwriting an existing
     one without asking).
  5. Builds and starts the stack, creates AllHaven's tables in Supabase when that
     is part of the chosen mode, waits for /health, and opens the app.

Everything runs in Docker, so the machine needs neither Python nor Node — only
Docker Desktop, which step 1 installs on request.

The everyday control panel then handles start/stop/restart, status, logs, ports,
switching the database mode, and re-running setup.

Run directly:  python setup\\windows\\allhaven_windows.py
Frozen build:  AllHaven-Setup.exe
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "AllHaven"
COMPOSE_FILES = ("docker-compose.prod.yml", "docker-compose.prod.local.yml")
ENV_FILE = ".env.prod"
HEALTH_PATH = "/api/v1/health"
DEFAULT_BACKEND_PORT = 8000
DEFAULT_FRONTEND_PORT = 3000

# winget package ids for the prerequisites we can install unattended.
PREREQS = {
    "docker": ("Docker Desktop", "Docker.DockerDesktop"),
}


# --------------------------------------------------------------------------- #
# Console presentation
# --------------------------------------------------------------------------- #

C = {
    "reset": "\033[0m", "dim": "\033[90m", "bold": "\033[1m",
    "cyan": "\033[36m", "green": "\033[32m", "yellow": "\033[33m",
    "red": "\033[31m", "blue": "\033[34m", "magenta": "\033[35m",
}
_ANSI = False

# Box-drawing glyphs, swapped for ASCII when the console cannot encode them
# (a redirected cmd.exe pipe still defaults to cp1252, which has none of these).
GLYPHS_UNICODE = {"tl": "╔", "tr": "╗", "bl": "╚", "br": "╝", "h": "═", "v": "║",
                  "line": "─", "ok": "✓", "warn": "!", "bad": "✗", "dot": "•"}
GLYPHS_ASCII = {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "=", "v": "|",
                "line": "-", "ok": "OK", "warn": "!", "bad": "X", "dot": "*"}
G = GLYPHS_ASCII


def _init_console() -> None:
    """Set up colour and pick a glyph set the output stream can actually encode."""
    global _ANSI, G
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        "".join(GLYPHS_UNICODE.values()).encode(sys.stdout.encoding or "ascii")
        G = GLYPHS_UNICODE
    except Exception:
        G = GLYPHS_ASCII
    _ANSI = _enable_ansi()


def _enable_ansi() -> bool:
    """Turn on virtual-terminal processing so ANSI colours render in cmd.exe."""
    if os.environ.get("NO_COLOR") is not None or not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def c(text: str, colour: str) -> str:
    return f"{C[colour]}{text}{C['reset']}" if _ANSI else text


def clear() -> None:
    # ANSI clear + home. Avoids spawning a shell just to blank the screen.
    print("\033[2J\033[H" if _ANSI else "\n" * 3, end="")


def banner(subtitle: str) -> None:
    width = 62
    print()
    print(c("  " + G["tl"] + G["h"] * width + G["tr"], "cyan"))
    print(c("  " + G["v"], "cyan") + c(f"{'A L L H A V E N':^{width}}", "bold") + c(G["v"], "cyan"))
    print(c("  " + G["v"], "cyan") + f"{subtitle:^{width}}" + c(G["v"], "cyan"))
    print(c("  " + G["bl"] + G["h"] * width + G["br"], "cyan"))
    print()


def rule(label: str = "") -> None:
    line = G["line"]
    print(c(f"  {line * 2} {label} " + line * max(0, 58 - len(label)), "dim") if label
          else c("  " + line * 62, "dim"))


def say(msg: str = "") -> None:
    print(f"  {msg}")


def good(msg: str) -> None:
    print("  " + c(G["ok"] + " ", "green") + msg)


def warn(msg: str) -> None:
    print("  " + c(G["warn"] + " ", "yellow") + msg)


def bad(msg: str) -> None:
    print("  " + c(G["bad"] + " ", "red") + msg)


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(c(f"  {prompt}{suffix}: ", "bold")).strip()
    except EOFError:
        return default
    return answer or default


def confirm(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = ask(f"{prompt} ({hint})").lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def pause() -> None:
    try:
        input(c("\n  Press Enter to continue…", "dim"))
    except EOFError:
        pass


def menu(title: str, entries: list[tuple[str, str]]) -> str:
    """Show a numbered menu and return the chosen key."""
    rule(title)
    for index, (_, label) in enumerate(entries, start=1):
        print(f"   {c(str(index), 'cyan')}. {label}")
    print()
    while True:
        choice = ask("Choose")
        if choice.isdigit() and 1 <= int(choice) <= len(entries):
            return entries[int(choice) - 1][0]
        warn(f"Enter a number between 1 and {len(entries)}.")


# --------------------------------------------------------------------------- #
# Repo + process helpers
# --------------------------------------------------------------------------- #

def repo_root() -> Path:
    """Directory holding docker-compose.prod.yml, searching upwards from this file."""
    base = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    for candidate in (base, *base.parents):
        if (candidate / COMPOSE_FILES[0]).exists():
            return candidate
    return base


ROOT = repo_root()


def run(argv: list[str], cwd: Path | None = None, capture: bool = True, timeout: int = 900):
    """Run a command; return (returncode, output). Never raises on a missing binary."""
    try:
        if capture:
            done = subprocess.run(  # noqa: S603
                argv, cwd=str(cwd or ROOT), capture_output=True, text=True,
                timeout=timeout, encoding="utf-8", errors="replace",
            )
            return done.returncode, (done.stdout or "") + (done.stderr or "")
        return subprocess.run(argv, cwd=str(cwd or ROOT), timeout=timeout).returncode, ""  # noqa: S603
    except FileNotFoundError:
        return 127, f"command not found: {argv[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s: {' '.join(argv)}"
    except OSError as exc:
        return 1, str(exc)


def compose(*args: str, capture: bool = True, timeout: int = 900):
    argv = ["docker", "compose"]
    for name in COMPOSE_FILES:
        argv += ["-f", name]
    argv += ["--env-file", ENV_FILE, *args]
    return run(argv, capture=capture, timeout=timeout)


def http_json(url: str, timeout: int = 5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (localhost)
            return json.loads(resp.read().decode() or "{}")
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Prerequisites
# --------------------------------------------------------------------------- #

def docker_installed() -> bool:
    return run(["docker", "--version"], timeout=20)[0] == 0


def docker_running() -> bool:
    return run(["docker", "info"], timeout=60)[0] == 0


def compose_available() -> bool:
    return run(["docker", "compose", "version"], timeout=30)[0] == 0


def winget_available() -> bool:
    return run(["winget", "--version"], timeout=30)[0] == 0


def check_prereqs() -> list[str]:
    """Print a prerequisite report and return the keys that are missing."""
    rule("Prerequisites")
    missing: list[str] = []
    if docker_installed():
        good("Docker Desktop is installed")
        if compose_available():
            good("Docker Compose is available")
        else:
            bad("Docker Compose is missing — update Docker Desktop")
            missing.append("docker")
    else:
        bad("Docker Desktop is NOT installed")
        missing.append("docker")
    return missing


def install_prereqs(missing: list[str]) -> bool:
    """Install the missing prerequisites through winget, after explicit consent."""
    if not missing:
        return True
    print()
    warn("These need to be installed first:")
    for key in missing:
        say(f'   {G["dot"]} {PREREQS[key][0]}')
    print()
    if not winget_available():
        bad("winget is not available on this machine, so nothing can be installed automatically.")
        say(c("   Install Docker Desktop manually: https://www.docker.com/products/docker-desktop/", "dim"))
        return False
    if not confirm("Install them now with winget? (needs administrator rights)"):
        say(c("   Skipped. Install them yourself, then run this again.", "dim"))
        return False

    for key in missing:
        label, package = PREREQS[key]
        say(f"\n  Installing {label} — this takes a few minutes…")
        code, _ = run(
            ["winget", "install", "--id", package, "-e", "--accept-package-agreements",
             "--accept-source-agreements"],
            capture=False, timeout=1800,
        )
        if code == 0:
            good(f"{label} installed")
        else:
            bad(f"{label} did not install (winget exit {code})")
            return False
    print()
    warn("Docker Desktop usually needs a sign-out or restart before it will start.")
    warn("Start Docker Desktop, wait for it to say 'Engine running', then run this again.")
    return False


def ensure_docker_running() -> bool:
    """Make sure the Docker engine is up, offering to launch Docker Desktop."""
    if docker_running():
        good("Docker engine is running")
        return True
    warn("Docker is installed but the engine is not running.")
    if confirm("Start Docker Desktop now?"):
        for path in (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Docker" / "Docker Desktop.exe",
        ):
            if path.exists():
                subprocess.Popen([str(path)])  # noqa: S603
                say("  Waiting for the Docker engine (up to 3 minutes)…")
                for _ in range(36):
                    time.sleep(5)
                    if docker_running():
                        good("Docker engine is running")
                        return True
                break
        bad("Docker Desktop did not come up in time. Start it manually, then run this again.")
    return False


# --------------------------------------------------------------------------- #
# Environment file
# --------------------------------------------------------------------------- #

def read_env() -> dict[str, str]:
    path = ROOT / ENV_FILE
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def is_configured() -> bool:
    env = read_env()
    return bool(env.get("SECRET_KEY")) and "change-me" not in env.get("SECRET_KEY", "")


# --------------------------------------------------------------------------- #
# Ports
# --------------------------------------------------------------------------- #

def port_of(name: str, fallback: int) -> int:
    raw = read_env().get(name, "")
    return int(raw) if raw.isdigit() and 1 <= int(raw) <= 65535 else fallback


def backend_url() -> str:
    return f"http://localhost:{port_of('BACKEND_PORT', DEFAULT_BACKEND_PORT)}"


def frontend_url() -> str:
    return f"http://localhost:{port_of('FRONTEND_PORT', DEFAULT_FRONTEND_PORT)}"


def port_free(port: int) -> bool:
    """True when nothing is listening on the port right now."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def first_free_port(start: int, taken: set[int]) -> int:
    port = start
    while port < 65535 and (port in taken or not port_free(port)):
        port += 1
    return port


def choose_ports(env: dict[str, str]) -> dict[str, str]:
    """Ask which host ports to publish on, warning about anything already in use."""
    rule("Ports")
    say("Which addresses should AllHaven answer on?")
    say(c("   Only the host side changes — inside Docker the containers keep their", "dim"))
    say(c("   own ports, so nothing else has to be reconfigured.", "dim"))
    print()

    chosen: dict[str, str] = {}
    taken: set[int] = set()
    for key, label, fallback in (
        ("FRONTEND_PORT", "Web app", DEFAULT_FRONTEND_PORT),
        ("BACKEND_PORT", "API", DEFAULT_BACKEND_PORT),
    ):
        current = int(env.get(key) or fallback)
        # A port AllHaven itself is already serving on is not a conflict.
        busy = not port_free(current) and not _ours(current)
        if busy:
            suggestion = first_free_port(current + 1, taken)
            warn(f"port {current} is already in use — {suggestion} is free")
            current = suggestion
        while True:
            answer = ask(f"{label} port", str(current))
            if not answer.isdigit() or not (1 <= int(answer) <= 65535):
                bad("Enter a number between 1 and 65535.")
                continue
            port = int(answer)
            if port in taken:
                bad("That port is already assigned to the other service.")
                continue
            if not port_free(port) and not _ours(port):
                if not confirm(f"Port {port} is in use. Use it anyway?", default=False):
                    continue
            chosen[key] = str(port)
            taken.add(port)
            break
    return chosen


def _ours(port: int) -> bool:
    """True when the listener on this port is already an AllHaven service."""
    payload = http_json(f"http://localhost:{port}{HEALTH_PATH}", timeout=2)
    return bool(payload and payload.get("data", {}).get("app") == "AllHaven Command Center")


# --------------------------------------------------------------------------- #
# Supabase — Management API (create a project) and credential entry
# --------------------------------------------------------------------------- #

SUPABASE_API = "https://api.supabase.com/v1"
SUPABASE_REGIONS = [
    ("ap-southeast-1", "Singapore"),
    ("ap-northeast-1", "Tokyo"),
    ("ap-south-1", "Mumbai"),
    ("ap-southeast-2", "Sydney"),
    ("us-east-1", "North Virginia"),
    ("us-west-1", "North California"),
    ("eu-west-2", "London"),
    ("eu-central-1", "Frankfurt"),
    ("sa-east-1", "São Paulo"),
]


def _api(token: str, method: str, path: str, body: dict | None = None, timeout: int = 60):
    """Call the Supabase Management API. Returns the parsed body, or {'_error': ...}."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{SUPABASE_API}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed API host)
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        return {"_error": f"HTTP {exc.code}: {exc.read().decode()[:200]}"}
    except Exception as exc:
        return {"_error": str(exc)}


def create_supabase_project() -> dict | None:
    """Create a Supabase project and return its url/keys/connection string.

    Uses a personal access token rather than storing account credentials; the token
    is used for this conversation only and never written to disk.
    """
    print()
    rule("Create a Supabase project")
    say("A personal access token lets AllHaven create the project for you.")
    say(c("   Get one at https://supabase.com/dashboard/account/tokens", "dim"))
    say(c("   It is used now and never saved to disk.", "dim"))
    print()
    token = ask("Personal access token").strip()
    if not token:
        bad("No token given.")
        return None

    orgs = _api(token, "GET", "/organizations")
    if isinstance(orgs, dict) and orgs.get("_error"):
        bad(f"Could not read your organisations — {orgs['_error']}")
        return None
    if not orgs:
        bad("That token has no organisations. Create one in the Supabase dashboard first.")
        return None
    org_id = orgs[0]["id"] if len(orgs) == 1 else menu(
        "Which organisation?", [(o["id"], o.get("name", o["id"])) for o in orgs]
    )

    name = ask("Project name", "AllHaven")
    region = menu("Which region?", [(rid, f"{label}  ({rid})") for rid, label in SUPABASE_REGIONS])
    db_password = secrets.token_urlsafe(24)

    say("\n  Creating the project — this takes a couple of minutes…")
    created = _api(token, "POST", "/projects", {
        "name": name, "organization_id": org_id, "region": region,
        "db_pass": db_password, "plan": "free",
    })
    if created.get("_error"):
        bad(f"Could not create the project — {created['_error']}")
        return None
    ref = created.get("id") or created.get("ref")
    if not ref:
        bad("Supabase did not return a project reference.")
        return None
    good(f"Project created ({ref})")

    say("  Waiting for it to finish provisioning…")
    for _ in range(60):  # up to ~5 minutes
        time.sleep(5)
        status = _api(token, "GET", f"/projects/{ref}").get("status", "")
        if status in ("ACTIVE_HEALTHY", "ACTIVE"):
            good("Project is ready")
            break
        if "FAILED" in status:
            bad(f"Provisioning failed ({status}).")
            return None
    else:
        warn("Still provisioning. It will come up on its own — re-run setup afterwards.")
        return None

    keys = _api(token, "GET", f"/projects/{ref}/api-keys")
    by_name = {k.get("name"): k.get("api_key", "") for k in keys} if isinstance(keys, list) else {}
    if not by_name.get("anon"):
        bad("Project created, but its API keys could not be read. Copy them from the dashboard.")
        return None

    return {
        "SUPABASE_URL": f"https://{ref}.supabase.co",
        "SUPABASE_ANON_KEY": by_name.get("anon", ""),
        "SUPABASE_SERVICE_ROLE_KEY": by_name.get("service_role", ""),
        "SUPABASE_JWT_SECRET": "",
        # Session pooler — the direct db.<ref>.supabase.co host is IPv6-only on new
        # projects, which Docker Desktop cannot reach by default.
        "SUPABASE_DB_URL": (
            f"postgresql://postgres.{ref}:{db_password}"
            f"@aws-0-{region}.pooler.supabase.com:5432/postgres"
        ),
    }


def ask_supabase_credentials(env: dict[str, str], need_dsn: bool) -> dict[str, str]:
    """Collect Supabase details for a project the user already has."""
    print()
    rule("Your Supabase project")
    say(c("   Dashboard → Settings → API", "dim"))
    print()
    updates = {
        "SUPABASE_URL": ask("Project URL", env.get("SUPABASE_URL", "")).strip(),
        "SUPABASE_ANON_KEY": ask("Anon key", env.get("SUPABASE_ANON_KEY", "")).strip(),
        "SUPABASE_SERVICE_ROLE_KEY": ask("Service role key", env.get("SUPABASE_SERVICE_ROLE_KEY", "")).strip(),
        "SUPABASE_JWT_SECRET": ask("JWT secret (optional — needed by the mobile app)",
                                   env.get("SUPABASE_JWT_SECRET", "")).strip(),
    }
    if need_dsn:
        print()
        say("Database connection string:")
        say(c("   Dashboard → Settings → Database → Connection string → URI (session pooler)", "dim"))
        say(c("   Used to create AllHaven's tables in your project.", "dim"))
        print()
        updates["SUPABASE_DB_URL"] = ask("Connection string", env.get("SUPABASE_DB_URL", "")).strip()
    return updates


def setup_supabase(env: dict[str, str], need_dsn: bool) -> dict[str, str]:
    """Point AllHaven at a Supabase project, creating one if the user has none."""
    print()
    have = menu("Do you already have a Supabase project?", [
        ("yes", "Yes — I will paste the details"),
        ("no", "No — create one for me"),
    ])
    if have == "no":
        created = create_supabase_project()
        if created:
            good("Supabase project configured")
            return created
        warn("Falling back to entering the details by hand.")
    return ask_supabase_credentials(env, need_dsn)


def choose_database(env: dict[str, str]) -> dict[str, str]:
    """Ask how data is stored and return the env keys that encode the answer."""
    rule("Database")
    say("Where should AllHaven keep your data?")
    print()
    mode = menu("Choose how data is stored", [
        ("both", "Both — local PostgreSQL + Supabase cloud   (recommended)"),
        ("local", "Local PostgreSQL only                     (no cloud, no mobile app)"),
        ("supabase", "Supabase cloud only                       (single cloud database)"),
    ])
    print()
    if mode == "both":
        say(c("   Data lives on this PC and mirrors to Supabase every 15 seconds.", "dim"))
        say(c("   Works offline, and your phone reads the cloud copy.", "dim"))
    elif mode == "local":
        say(c("   Everything stays on this PC. Nothing leaves the machine.", "dim"))
    else:
        say(c("   The Supabase project IS the database, so there is nothing to mirror.", "dim"))
        say(c("   Needs a working internet connection to use AllHaven at all.", "dim"))

    updates: dict[str, str] = {
        # Blank DATABASE_URL lets compose point the backend at the db container.
        "DATABASE_URL": "", "ALLHAVEN_DB_TARGET": "",
        "SUPABASE_URL": "", "SUPABASE_ANON_KEY": "", "SUPABASE_SERVICE_ROLE_KEY": "",
        "SUPABASE_JWT_SECRET": "", "SUPABASE_DB_URL": "",
    }
    if mode == "local":
        return updates

    # 'both' needs the connection string only to create the tables in Supabase;
    # 'supabase' needs it as the actual database.
    updates.update(setup_supabase(env, need_dsn=True))
    if not updates.get("SUPABASE_URL"):
        bad("No Supabase project configured — continuing with local PostgreSQL only.")
        return {k: "" for k in updates}

    if mode == "supabase":
        dsn = updates.get("SUPABASE_DB_URL", "")
        if not dsn:
            bad("Supabase-only needs a connection string. Using both instead.")
        else:
            # SQLAlchemy needs the driver named explicitly.
            if dsn.startswith("postgresql://"):
                dsn = dsn.replace("postgresql://", "postgresql+psycopg://", 1)
            updates["DATABASE_URL"] = dsn
            # RLS matters here: this database is reachable with the anon key.
            updates["ALLHAVEN_DB_TARGET"] = "supabase"
    return updates


def write_env(updates: dict[str, str]) -> None:
    """Create or update .env.prod, backing up any existing file first."""
    path = ROOT / ENV_FILE
    env = read_env()

    if path.exists():
        backup = path.with_suffix(f".prod.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        say(c(f"   previous {ENV_FILE} backed up to {backup.name}", "dim"))

    defaults = {
        "DOMAIN": "localhost",
        "APP_TIMEZONE": "Asia/Jakarta",
        "POSTGRES_USER": "allhaven",
        "POSTGRES_PASSWORD": env.get("POSTGRES_PASSWORD") or secrets.token_urlsafe(24),
        "POSTGRES_DB": "allhaven",
        "SECRET_KEY": env.get("SECRET_KEY") or secrets.token_urlsafe(48),
        "SETTINGS_ENCRYPTION_KEY": env.get("SETTINGS_ENCRYPTION_KEY") or secrets.token_urlsafe(48),
        "API_DOCS_ENABLED": "false",
        "ALLOW_PRIVATE_INTEGRATION_URLS": "false",
        "SESSION_TTL_DAYS": "7",
        "AUTH_RATE_LIMIT_PER_MINUTE": "10",
        "SUPABASE_URL": "",
        "SUPABASE_ANON_KEY": "",
        "SUPABASE_SERVICE_ROLE_KEY": "",
        "SUPABASE_JWT_SECRET": "",
        # PostgreSQL connection string for the Supabase project. Used to create
        # AllHaven's tables there; also the live database in Supabase-only mode.
        "SUPABASE_DB_URL": "",
        # Auto sync always on. It is ignored automatically when Supabase is the
        # primary database — there is nothing to mirror in that mode.
        "SYNC_INTERVAL_SECONDS": "15",
        "DATABASE_URL": "",
        "ALLHAVEN_DB_TARGET": "",
        # Host ports. Only the outside changes; containers keep 3000/8000 internally.
        "FRONTEND_PORT": str(DEFAULT_FRONTEND_PORT),
        "BACKEND_PORT": str(DEFAULT_BACKEND_PORT),
        "OLLAMA_BASE_URL": "",
        "DRIVE_MAX_UPLOAD_MB": "250",
    }
    merged = {**defaults, **{k: v for k, v in env.items() if k in defaults}, **updates}

    lines = [
        f"# {APP_NAME} production environment — generated by the Windows installer.",
        "# NEVER commit this file: it holds your secrets.",
        f"# Written {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    lines += [f"{key}={merged[key]}" for key in defaults]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    good(f"{ENV_FILE} written")


def primary_db_mode() -> str:
    """Which database the app writes to."""
    return "supabase" if ".supabase." in read_env().get("DATABASE_URL", "") else "local"


def storage_mode() -> str:
    """How data is stored overall: 'both', 'local', or 'supabase'."""
    env = read_env()
    if ".supabase." in env.get("DATABASE_URL", ""):
        return "supabase"
    return "both" if env.get("SUPABASE_URL") else "local"


def bootstrap_supabase_schema() -> bool:
    """Create AllHaven's tables (and RLS policies) in the Supabase project.

    Only needed in 'both' mode: there the backend migrates the local database, so
    nothing else ever touches Supabase — and a brand-new project has no tables at
    all, which makes every mirror pass fail. In Supabase-only mode the backend's
    own startup migration already covers it.
    """
    env = read_env()
    dsn = env.get("SUPABASE_DB_URL", "")
    if not dsn or storage_mode() != "both":
        return True
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+psycopg://", 1)

    say("  Creating AllHaven's tables in Supabase (with row-level security)…")
    code, out = compose(
        "run", "--rm", "--no-deps",
        "-e", f"DATABASE_URL={dsn}",
        "-e", "ALLHAVEN_DB_TARGET=supabase",
        "backend", "alembic", "upgrade", "head",
        timeout=900,
    )
    if code == 0:
        good("Supabase schema is up to date")
        return True
    bad("Could not migrate the Supabase project.")
    for line in (out or "").strip().splitlines()[-6:]:
        say(c("   " + line[:150], "dim"))
    say(c("   The app still works; the mirror stays idle until this succeeds.", "dim"))
    return False


def services() -> list[str]:
    """Which containers to run. Supabase-primary installs need no local database."""
    return ["backend", "frontend"] if primary_db_mode() == "supabase" else ["db", "backend", "frontend"]


# --------------------------------------------------------------------------- #
# Stack control
# --------------------------------------------------------------------------- #

def wait_healthy(timeout: int = 240) -> dict | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = http_json(f"{backend_url()}{HEALTH_PATH}")
        if payload and payload.get("data", {}).get("status") == "ok":
            return payload["data"]
        time.sleep(3)
    return None


def start_stack(build: bool = False) -> bool:
    args = ["up", "-d"] + (["--build"] if build else []) + services()
    say("  Starting containers" + (" (building images — first run takes a while)…" if build else "…"))
    code, _ = compose(*args, capture=False, timeout=3600)
    if code != 0:
        bad(f"docker compose failed (exit {code})")
        return False
    say("  Waiting for the backend to report healthy…")
    health = wait_healthy()
    if not health:
        if db_password_rejected() and offer_database_reset():
            return start_stack(build=build)
        bad("Backend did not become healthy in time. Check the logs from the control panel.")
        return False
    good(f"{APP_NAME} {health.get('app_version', '')} is running "
         f"(database: {health.get('primary_db')}, sync every {health.get('sync_interval_seconds')}s)")
    return True


def db_password_rejected() -> bool:
    """True when the backend is failing because PostgreSQL refused its password.

    PostgreSQL only applies POSTGRES_PASSWORD when it initialises an empty data
    directory, so a reinstall that mints fresh secrets cannot open the database
    volume the previous install created. The symptom — a backend crash-loop — is
    otherwise very hard to read.
    """
    _, out = compose("logs", "--tail", "80", "backend")
    return "password authentication failed" in (out or "")


def offer_database_reset() -> bool:
    """Explain the credential mismatch and, if allowed, recreate the data volume."""
    print()
    bad("PostgreSQL rejected the password in " + ENV_FILE + ".")
    say("   The database volume was created by an earlier install, with a different")
    say("   password. PostgreSQL never changes it afterwards, so the two no longer")
    say("   match. Either restore the old " + ENV_FILE + ", or reset the database.")
    print()
    warn("Resetting DELETES everything in the local database.")
    if primary_db_mode() == "local":
        warn("Anything already mirrored to Supabase is pulled back after the reset.")
    if not confirm("Reset the local database now?", default=False):
        return False
    say("  Removing containers and the data volume…")
    compose("down", "-v", capture=False, timeout=600)
    good("Database reset — starting again with a clean volume")
    return True


def stop_stack() -> None:
    say("  Stopping containers…")
    compose("stop", capture=False, timeout=300)
    good("Stopped")


def show_status() -> None:
    rule("Status")
    health = http_json(f"{backend_url()}{HEALTH_PATH}")
    if health:
        data = health.get("data", {})
        good(f"Backend healthy — version {data.get('app_version')} ({data.get('env')})")
        modes = {"both": "local PostgreSQL + Supabase mirror",
                 "local": "local PostgreSQL only",
                 "supabase": "Supabase cloud only"}
        say(f"   Storage          : {c(modes[storage_mode()], 'magenta')}")
        say(f"   Writes go to     : {data.get('primary_db', '?')}")
        interval = data.get("sync_interval_seconds", 0)
        say("   Auto sync        : " + (c(f"on, every {interval}s", "green") if interval
                                        else c("nothing to mirror in this mode", "dim")))
    else:
        bad("Backend is not responding")
    frontend_up = http_json(frontend_url()) is not None
    say(f"   Web app          : {frontend_url()}")
    say(f"   API              : {backend_url()}")
    print()
    code, out = compose("ps", "--format", "table {{.Service}}\t{{.Status}}")
    if code == 0 and out.strip():
        for line in out.strip().splitlines():
            say("   " + line)
    _ = frontend_up


def show_logs() -> None:
    rule("Recent backend logs")
    code, out = compose("logs", "--tail", "60", "backend")
    for line in (out or "").splitlines()[-60:]:
        say("   " + line[:160])
    if code != 0:
        bad("Could not read logs — is the stack running?")


def open_app() -> None:
    url = frontend_url()
    webbrowser.open(url)
    good(f"Opened {url}")


# --------------------------------------------------------------------------- #
# Flows
# --------------------------------------------------------------------------- #

def run_setup() -> bool:
    clear()
    banner("First-time setup · Windows")
    say("This sets up everything AllHaven needs and starts it.")
    print()

    missing = check_prereqs()
    if missing and not install_prereqs(missing):
        return False
    if not ensure_docker_running():
        return False
    if not check_single_install():
        return False

    print()
    env = read_env()
    if is_configured() and not confirm(f"{ENV_FILE} already exists. Reconfigure it?", default=False):
        say(c("   Keeping the existing configuration.", "dim"))
    else:
        updates = choose_ports(env)
        print()
        updates.update(choose_database(env))
        write_env(updates)

    print()
    rule("Build and start")
    if not start_stack(build=True):
        return False

    print()
    bootstrap_supabase_schema()

    print()
    create_shortcut()
    print()
    good("Setup complete.")
    if confirm("Open AllHaven now?"):
        open_app()
    return True


def check_single_install() -> bool:
    """Warn when another AllHaven folder already owns the containers on this machine.

    All copies share one Compose project name, so a second folder does not get its
    own stack — it takes over the first one's containers while carrying different
    secrets, which locks the backend out of the existing database volume.
    """
    code, out = run(
        ["docker", "inspect", "allhaven-prod-db-1", "--format",
         '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'],
        timeout=30,
    )
    if code != 0 or not out.strip():
        return True  # nothing installed yet
    other = Path(out.strip())
    try:
        same = other.resolve() == ROOT.resolve()
    except OSError:
        same = False
    if same:
        return True
    print()
    warn(f"{APP_NAME} is already installed and running from another folder:")
    say(c(f"     {other}", "dim"))
    say("   Both folders share one set of containers, so continuing here takes them")
    say("   over. Its database keeps working only if this folder has the same secrets.")
    print()
    return confirm("Take over the existing installation?", default=False)


def create_shortcut() -> None:
    """Put an AllHaven shortcut on the Desktop, pointing at this program."""
    if os.name != "nt":
        return
    target = sys.executable if getattr(sys, "frozen", False) else str(ROOT / "AllHaven.bat")
    desktop = Path(os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"))
    if not desktop.is_dir():
        return
    link = desktop / f"{APP_NAME}.lnk"
    script = (
        f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut("{link}");'
        f'$s.TargetPath="{target}";$s.WorkingDirectory="{ROOT}";'
        f'$s.Description="{APP_NAME} Command Center";$s.Save()'
    )
    code, _ = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout=60)
    (good if code == 0 else warn)(
        f"Desktop shortcut created ({link.name})" if code == 0 else "Could not create the desktop shortcut"
    )


def change_ports() -> None:
    clear()
    banner("Change ports")
    say(f"Currently  web app {frontend_url()}   ·   API {backend_url()}")
    print()
    updates = choose_ports(read_env())
    if not updates:
        return
    write_env(updates)
    print()
    warn("The web app has the API address compiled into it, so the frontend image")
    warn("must be rebuilt for a new backend port to take effect.")
    if confirm("Rebuild and restart now?"):
        compose("down", capture=False, timeout=300)
        start_stack(build=True)


def change_database_mode() -> None:
    clear()
    banner("Change where data is stored")
    warn("Switching moves where new data is written. Existing rows are not migrated,")
    warn("so export anything you need before changing this on a live install.")
    print()
    if not confirm("Continue?", default=False):
        return
    write_env(choose_database(read_env()))
    print()
    if confirm("Restart AllHaven now so the change takes effect?"):
        compose("down", capture=False, timeout=300)
        if start_stack(build=False):
            bootstrap_supabase_schema()


def control_panel() -> None:
    while True:
        clear()
        health = http_json(f"{backend_url()}{HEALTH_PATH}")
        state = c("running", "green") if health else c("stopped", "yellow")
        banner(f"Control Panel · {storage_mode()} · {state}")

        action = menu("What would you like to do?", [
            ("open", "Open AllHaven in the browser"),
            ("start", "Start AllHaven"),
            ("stop", "Stop AllHaven"),
            ("restart", "Restart AllHaven"),
            ("status", "Status and auto-sync"),
            ("logs", "View recent logs"),
            ("ports", "Change ports"),
            ("database", "Change where data is stored"),
            ("setup", "Re-run setup / repair"),
            ("quit", "Exit"),
        ])

        print()
        if action == "open":
            open_app()
        elif action == "start":
            start_stack(build=False)
        elif action == "stop":
            stop_stack()
        elif action == "restart":
            stop_stack()
            start_stack(build=False)
        elif action == "status":
            show_status()
        elif action == "logs":
            show_logs()
        elif action == "ports":
            change_ports()
        elif action == "database":
            change_database_mode()
        elif action == "setup":
            run_setup()
        elif action == "quit":
            return
        pause()


def main() -> int:
    _init_console()

    if os.name != "nt":
        print("This program is for Windows. On Linux/macOS use ./install.sh and ./allhaven.sh.")
        return 1
    if not (ROOT / COMPOSE_FILES[0]).exists():
        clear()
        banner("Setup")
        bad(f"Could not find {COMPOSE_FILES[0]}.")
        say(f"   Put this program inside the {APP_NAME} folder and run it again.")
        say(f"   Looked in: {ROOT}")
        pause()
        return 1

    if "--setup" in sys.argv or not is_configured():
        if not run_setup():
            pause()
            return 1
        pause()
    control_panel()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n  Cancelled.")
        raise SystemExit(130)
