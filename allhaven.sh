#!/usr/bin/env bash
# =============================================================================
# AllHaven Command Center — run & control helper (use AFTER ./install.sh)
#
# Usage (run from the repo root):
#   ./allhaven.sh start                 # background: backend + frontend + agent
#   ./allhaven.sh run                   # foreground (Ctrl+C stops everything)
#   ./allhaven.sh stop                  # stop everything this script started
#   ./allhaven.sh restart [target]      # restart  all | backend | frontend | agent
#   ./allhaven.sh status                # what's running + ports
#   ./allhaven.sh port [svc] [number]   # show or set ports (frontend|backend|postgres|agent)
#   ./allhaven.sh setup                 # re-run setup (.env, deps, DB migration)
#   ./allhaven.sh ollama [model]        # check Ollama; optionally pull a model
#
# Fresh install? Use ./install.sh instead (this assumes you're already set up).
#
# Robust by design: start/stop/restart force-free the service ports, so a stale
# or wedged dev server can't block a restart. Safe by design: never prints or
# commits secrets, never deletes Docker volumes, and never touches the Postgres
# port (your database is left alone).
# =============================================================================

set -euo pipefail

# Resolve repo root (the directory containing this script).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PID_DIR="$ROOT/.allhaven-pids"
LOG_DIR="$ROOT/var/logs"
VENV_PY="$ROOT/backend/.venv/bin/python"

c_green() { printf '\033[0;32m%s\033[0m\n' "$1"; }
c_blue()  { printf '\033[0;36m%s\033[0m\n' "$1"; }
c_warn()  { printf '\033[0;33m%s\033[0m\n' "$1"; }
c_err()   { printf '\033[0;31m%s\033[0m\n' "$1" >&2; }

need() { command -v "$1" >/dev/null 2>&1; }

require_tools() {
  local missing=0
  for t in python3 node npm; do
    if ! need "$t"; then c_err "Missing required tool: $t"; missing=1; fi
  done
  [ "$missing" -eq 0 ] || { c_err "Please install the missing tools and retry."; exit 1; }
}

# -----------------------------------------------------------------------------
# Ports — single source of truth is .env; an exported shell var still wins.
# -----------------------------------------------------------------------------
_env_get() {  # _env_get KEY -> value from $ROOT/.env (last match), else empty
  [ -f "$ROOT/.env" ] || return 0
  grep -E "^$1=" "$ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"'" || true
}

load_ports() {
  BACKEND_PORT="${BACKEND_PORT:-$(_env_get BACKEND_PORT)}";    BACKEND_PORT="${BACKEND_PORT:-8000}"
  FRONTEND_PORT="${FRONTEND_PORT:-$(_env_get FRONTEND_PORT)}"; FRONTEND_PORT="${FRONTEND_PORT:-3000}"
  POSTGRES_PORT="${POSTGRES_PORT:-$(_env_get POSTGRES_PORT)}"; POSTGRES_PORT="${POSTGRES_PORT:-5432}"
  AGENT_PORT="${HAVEN_AGENT_PORT:-$(_env_get HAVEN_AGENT_PORT)}"; AGENT_PORT="${AGENT_PORT:-8765}"
}
load_ports

# -----------------------------------------------------------------------------
# Port helpers — find/kill whatever LISTENS on a TCP port (ss → lsof → fuser).
# Used so a stale/wedged server can't block a restart. NEVER call on Postgres.
# -----------------------------------------------------------------------------
# Pure-/proc PID-by-port finder (no external tools). Last-resort fallback so
# force-freeing a port works even where ss/lsof/fuser are absent.
_pids_on_port_py() {  # _pids_on_port_py <port>
  need python3 || return 0
  python3 - "$1" <<'PY'
import glob, os, sys
port = int(sys.argv[1])
inodes = set()
for proto in ("tcp", "tcp6"):
    try:
        rows = open(f"/proc/net/{proto}").read().splitlines()[1:]
    except OSError:
        continue
    for r in rows:
        f = r.split()
        if len(f) < 10 or f[3] != "0A":   # 0A = LISTEN
            continue
        if int(f[1].rsplit(":", 1)[1], 16) == port:
            inodes.add(f[9])
if not inodes:
    sys.exit(0)
pids = set()
for fd in glob.glob("/proc/[0-9]*/fd/*"):
    try:
        link = os.readlink(fd)
    except OSError:
        continue
    if link.startswith("socket:[") and link[8:-1] in inodes:
        pids.add(fd.split("/")[2])
print(" ".join(sorted(pids, key=int)))
PY
}

_pids_on_port() {  # _pids_on_port <port> -> listening pids, one per line
  local port="$1" pids=""
  if need ss; then
    pids="$(ss -ltnpH "( sport = :$port )" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"
  fi
  if [ -z "$pids" ] && need lsof; then
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
  fi
  if [ -z "$pids" ] && need fuser; then
    pids="$(fuser "$port/tcp" 2>/dev/null | tr -s ' ' '\n' | grep -E '^[0-9]+$' | sort -u || true)"
  fi
  if [ -z "$pids" ]; then
    pids="$(_pids_on_port_py "$port" || true)"
  fi
  printf '%s' "$pids"
}

_port_busy() { [ -n "$(_pids_on_port "$1")" ]; }

_free_port() {  # _free_port <port> — stop any listener (process group, then pid)
  local port="$1" pid
  for pid in $(_pids_on_port "$port"); do
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  done
}

# -----------------------------------------------------------------------------
# .env bootstrap (generates strong secrets once; never overwrites existing)
# -----------------------------------------------------------------------------
ensure_env() {
  if [ ! -f "$ROOT/.env" ]; then
    c_blue "Creating .env from .env.example with fresh secrets…"
    cp "$ROOT/.env.example" "$ROOT/.env"
    local secret enc
    secret="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
    enc="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
    # Replace the placeholder values.
    python3 - "$ROOT/.env" "$secret" "$enc" <<'PY'
import sys, re
path, secret, enc = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path).read()
def setval(t, key, val):
    return re.sub(rf'(?m)^{key}=.*$', f'{key}={val}', t)
text = setval(text, 'SECRET_KEY', secret)
text = setval(text, 'SETTINGS_ENCRYPTION_KEY', enc)
# Allow both localhost and 127.0.0.1 origins to avoid CORS confusion.
text = setval(text, 'BACKEND_CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
open(path, 'w').write(text)
PY
    c_green ".env created (SECRET_KEY + SETTINGS_ENCRYPTION_KEY generated)."
  else
    c_blue ".env already exists — keeping it."
  fi
  # The backend reads ./backend/.env when run from the backend folder.
  cp -f "$ROOT/.env" "$ROOT/backend/.env"
  # Frontend dev needs its own env file (points at the backend API).
  if [ ! -f "$ROOT/frontend/.env.local" ]; then
    cp "$ROOT/frontend/.env.local.example" "$ROOT/frontend/.env.local"
  fi
}

# -----------------------------------------------------------------------------
# .env editing helpers (used by `port`). Backup once; replace-or-append.
# -----------------------------------------------------------------------------
_set_env_kv() {  # _set_env_kv <file> <KEY> <VALUE>
  local file="$1" key="$2" val="$3"
  python3 - "$file" "$key" "$val" <<'PY'
import sys, re
path, key, val = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    text = open(path).read()
except FileNotFoundError:
    text = ""
pat = re.compile(rf'(?m)^{re.escape(key)}=.*$')
if pat.search(text):
    text = pat.sub(f'{key}={val}', text)
else:
    if text and not text.endswith('\n'):
        text += '\n'
    text += f'{key}={val}\n'
open(path, 'w').write(text)
PY
}

_update_database_url_port() {  # rewrite the :PORT in DATABASE_URL inside .env
  python3 - "$ROOT/.env" "$1" <<'PY'
import sys, re
path, port = sys.argv[1], sys.argv[2]
text = open(path).read()
text = re.sub(r'(?m)^(DATABASE_URL=.*?:)\d+(/)', rf'\g<1>{port}\g<2>', text)
open(path, 'w').write(text)
PY
}

# -----------------------------------------------------------------------------
# PostgreSQL (Docker preferred; otherwise assume a local server on :5432)
# -----------------------------------------------------------------------------
# True if something already accepts TCP on the Postgres port (native or container).
_pg_up() { (exec 3<>"/dev/tcp/127.0.0.1/${POSTGRES_PORT}") 2>/dev/null; }

ensure_postgres() {
  # Already serving (e.g. a native/systemd PostgreSQL)? Use it — don't fight Docker
  # for the port (that produced "address already in use" + a 30s wait on a
  # container that never started).
  if _pg_up; then
    c_green "PostgreSQL already running on :${POSTGRES_PORT} — using it."
    return 0
  fi
  if need docker && docker compose version >/dev/null 2>&1; then
    c_blue "Starting PostgreSQL via Docker Compose…"
    if docker compose up -d postgres >/dev/null 2>&1; then
      for _ in $(seq 1 30); do
        if _pg_up; then c_green "PostgreSQL is ready."; return 0; fi
        sleep 1
      done
      c_warn "PostgreSQL did not report ready in time; continuing anyway."
    else
      c_warn "Docker couldn't start PostgreSQL (port ${POSTGRES_PORT} may be held by a local one)."
      c_warn "Continuing — AllHaven will use whatever PostgreSQL is on :${POSTGRES_PORT}."
    fi
  else
    c_warn "Docker not found. Assuming a local PostgreSQL is running on :${POSTGRES_PORT}"
    c_warn "with user/pass/db = allhaven/allhaven/allhaven (see .env to change)."
  fi
}

# -----------------------------------------------------------------------------
# Backend / Frontend setup
# -----------------------------------------------------------------------------
setup_backend() {
  c_blue "Setting up backend (venv + dependencies)…"
  cd "$ROOT/backend"
  [ -d .venv ] || python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip >/dev/null
  pip install -r requirements.txt
  c_blue "Applying database migrations (alembic upgrade head)…"
  alembic upgrade head
  deactivate
  cd "$ROOT"
  c_green "Backend ready."
}

setup_frontend() {
  c_blue "Installing frontend dependencies…"
  cd "$ROOT/frontend"
  [ -d node_modules ] || npm install
  cd "$ROOT"
  c_green "Frontend ready."
}

cmd_setup() {
  require_tools
  ensure_env
  ensure_postgres
  setup_backend
  setup_frontend
  c_green "Setup complete. Run:  ./allhaven.sh start   (or  run  for foreground)"
}

# -----------------------------------------------------------------------------
# Background start/stop primitives. Each service runs in its own session
# (setsid) so we can kill the whole process group — important for the frontend,
# where `npm` spawns a `next-server` child.
# -----------------------------------------------------------------------------
_is_running() {  # _is_running <name>
  local f="$PID_DIR/$1.pid"
  [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null
}

_start_bg() {  # _start_bg <name> <port> <command...>
  local name="$1" port="$2"; shift 2
  mkdir -p "$PID_DIR" "$LOG_DIR"
  if _is_running "$name"; then c_warn "$name already running (pid $(cat "$PID_DIR/$name.pid"))."; return 0; fi
  _free_port "$port"   # clear any stale/wedged server squatting on the port
  setsid "$@" >"$LOG_DIR/$name.log" 2>&1 < /dev/null &
  echo $! > "$PID_DIR/$name.pid"
  c_green "$name started (pid $!) — logs: $LOG_DIR/$name.log"
}

_stop_one() {  # _stop_one <name>
  # NB: declare on separate lines — `local a=$1 b=$a` expands $a (here $name)
  # BEFORE local assigns it, which trips `set -u` with "name: unbound variable".
  local name="$1" f pid
  f="$PID_DIR/$name.pid"
  if [ ! -f "$f" ]; then return 0; fi
  pid="$(cat "$f" 2>/dev/null || true)"
  # Only signal a numeric pid that is still alive — guards against a corrupt pid
  # file and against PID reuse signalling an unrelated process group.
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true   # kill the whole group, then fall back
    c_green "$name stopped."
  fi
  rm -f "$f"
}

# Service commands (shared by start / restart).
start_backend_bg() {
  _start_bg backend "$BACKEND_PORT" bash -c \
    "cd '$ROOT/backend' && source .venv/bin/activate && alembic upgrade head >/dev/null 2>&1 && exec uvicorn app.main:app --host 0.0.0.0 --port '$BACKEND_PORT'"
}
start_frontend_bg() {
  _start_bg frontend "$FRONTEND_PORT" bash -c \
    "cd '$ROOT/frontend' && exec npm run dev -- -H 0.0.0.0 -p '$FRONTEND_PORT'"
}
start_agent_bg() {  # local control agent for the in-app System Control panel (127.0.0.1 only)
  [ -x "$VENV_PY" ] || return 0   # best-effort; agent needs the backend venv
  _start_bg agent "$AGENT_PORT" "$VENV_PY" "$ROOT/installer/haven_agent.py"
}

# Best-effort LAN IP. The trailing `|| true` keeps a failed `hostname` from
# tripping `set -e`/`pipefail` (which would otherwise abort start/run).
_lan_ip() { { hostname -I 2>/dev/null || true; } | awk '{print $1}' || true; }

# -----------------------------------------------------------------------------
# run — foreground (backend + agent in background, frontend in foreground)
# -----------------------------------------------------------------------------
cmd_run() {
  require_tools
  ensure_env
  ensure_postgres
  [ -d "$ROOT/backend/.venv" ] || setup_backend
  [ -d "$ROOT/frontend/node_modules" ] || setup_frontend

  mkdir -p "$PID_DIR" "$LOG_DIR"
  _free_port "$BACKEND_PORT"   # clear a wedged backend before we bind

  c_blue "Starting backend on http://localhost:${BACKEND_PORT} …"
  ( cd "$ROOT/backend" && source .venv/bin/activate \
      && alembic upgrade head >/dev/null 2>&1 \
      && exec uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT}" ) &
  echo $! > "$PID_DIR/backend.pid"
  start_agent_bg   # local control agent so the in-app System Control panel works

  cleanup() {
    echo
    c_warn "Stopping servers…"
    [ -f "$PID_DIR/backend.pid" ] && kill "$(cat "$PID_DIR/backend.pid")" 2>/dev/null || true
    rm -f "$PID_DIR/backend.pid"
    _stop_one agent
  }
  trap cleanup EXIT INT TERM

  sleep 3
  c_green "Backend up. Open the app at:  http://localhost:${FRONTEND_PORT}"
  local lan; lan="$(_lan_ip)"
  if [ -n "$lan" ]; then
    c_green "On other devices (same Wi-Fi):  http://${lan}:${FRONTEND_PORT}"
    c_warn  "The API base auto-follows the host, so phones/tablets just work — no rebuild."
  fi
  c_warn  "Tip: use http://localhost (not 127.0.0.1) on this machine."
  c_blue "Starting frontend (dev, reachable on your LAN)… press Ctrl+C to stop everything."
  _free_port "$FRONTEND_PORT"   # clear a wedged frontend before we bind
  cd "$ROOT/frontend"
  npm run dev -- -H 0.0.0.0 -p "${FRONTEND_PORT}"
}

# -----------------------------------------------------------------------------
# start — everything in the background
# -----------------------------------------------------------------------------
cmd_start() {
  require_tools; ensure_env; ensure_postgres
  [ -d "$ROOT/backend/.venv" ] || setup_backend
  [ -d "$ROOT/frontend/node_modules" ] || setup_frontend
  start_backend_bg
  start_agent_bg
  sleep 2
  start_frontend_bg
  c_green "All services starting in the background. Open:  http://localhost:${FRONTEND_PORT}"
  local lan; lan="$(_lan_ip)"
  [ -n "$lan" ] && c_green "On the LAN / phone (same Wi-Fi):  http://${lan}:${FRONTEND_PORT}"
  c_blue "First load compiles routes (a few seconds). Stop:  ./allhaven.sh stop  ·  Restart:  ./allhaven.sh restart"
}

# -----------------------------------------------------------------------------
# stop — everything this script started (and clear the ports as a fallback)
# -----------------------------------------------------------------------------
cmd_stop() {
  _stop_one frontend
  _stop_one backend
  _stop_one agent
  # Fallback: clear anything still squatting on our ports (stale/untracked
  # servers from an earlier run). Postgres is intentionally left untouched.
  _free_port "$FRONTEND_PORT"
  _free_port "$BACKEND_PORT"
  _free_port "$AGENT_PORT"
  c_green "Stopped backend + frontend + agent (database left running)."
}

# -----------------------------------------------------------------------------
# restart — all | backend | frontend | agent
# -----------------------------------------------------------------------------
cmd_restart() {
  local target="${1:-all}"
  require_tools
  case "$target" in
    all)
      c_blue "Restarting AllHaven (backend + frontend + agent)…"
      cmd_stop; sleep 1; cmd_start ;;
    backend|be)
      ensure_postgres
      c_blue "Restarting backend on :${BACKEND_PORT}…"
      _stop_one backend; _free_port "$BACKEND_PORT"; sleep 1; start_backend_bg
      # Ensure the control agent is up too, so Settings → System Control can
      # start/stop/restart services after a bare backend restart (no-op if already up).
      start_agent_bg ;;
    frontend|fe|front)
      c_blue "Restarting frontend on :${FRONTEND_PORT}…"
      _stop_one frontend; _free_port "$FRONTEND_PORT"; sleep 1; start_frontend_bg
      c_warn "First load recompiles routes — give it a few seconds before refreshing." ;;
    agent)
      c_blue "Restarting control agent on 127.0.0.1:${AGENT_PORT}…"
      _stop_one agent; _free_port "$AGENT_PORT"; sleep 1; start_agent_bg ;;
    *)
      c_err "Unknown restart target: $target"
      echo "Use one of:  all | backend | frontend | agent" >&2
      exit 1 ;;
  esac
}

# -----------------------------------------------------------------------------
# status — what's running, on which ports
# -----------------------------------------------------------------------------
_status_line() {  # _status_line <name> <port>
  local name="$1" port="$2" state
  if _is_running "$name"; then
    state="running (pid $(cat "$PID_DIR/$name.pid"))"
  elif _port_busy "$port"; then
    state="running (untracked, holding :$port)"
  else
    state="stopped"
  fi
  printf '  %-9s :%-5s %s\n' "$name" "$port" "$state"
}

cmd_status() {
  c_blue "AllHaven status:"
  _status_line backend  "$BACKEND_PORT"
  _status_line frontend "$FRONTEND_PORT"
  _status_line agent    "$AGENT_PORT"
  if _port_busy "$POSTGRES_PORT"; then
    printf '  %-9s :%-5s %s\n' postgres "$POSTGRES_PORT" "running (Docker or native)"
  else
    printf '  %-9s :%-5s %s\n' postgres "$POSTGRES_PORT" "not reachable"
  fi
}

# -----------------------------------------------------------------------------
# port — show or set service ports (writes .env; apply with `restart`)
# -----------------------------------------------------------------------------
cmd_port() {
  local svc="${1:-}" val="${2:-}"
  if [ -z "$svc" ]; then
    c_blue "Current ports (from .env):"
    printf '  %-9s %s\n' frontend "$FRONTEND_PORT"
    printf '  %-9s %s\n' backend  "$BACKEND_PORT"
    printf '  %-9s %s\n' postgres "$POSTGRES_PORT"
    printf '  %-9s %s\n' agent    "$AGENT_PORT (127.0.0.1 only)"
    echo
    echo "Change one:  ./allhaven.sh port <frontend|backend|postgres|agent> <number>"
    echo "Then apply:  ./allhaven.sh restart"
    return 0
  fi
  local key
  case "$svc" in
    frontend|fe)    key="FRONTEND_PORT" ;;
    backend|be)     key="BACKEND_PORT" ;;
    postgres|pg|db) key="POSTGRES_PORT" ;;
    agent)          key="HAVEN_AGENT_PORT" ;;
    *) c_err "Unknown service: $svc (use frontend|backend|postgres|agent)"; exit 1 ;;
  esac
  if [ -z "$val" ]; then c_err "Missing port number.  e.g.  ./allhaven.sh port $svc 3001"; exit 1; fi
  if ! [[ "$val" =~ ^[0-9]+$ ]] || [ "$val" -lt 1 ] || [ "$val" -gt 65535 ]; then
    c_err "Invalid port '$val' (must be 1–65535)."; exit 1
  fi
  ensure_env
  cp -f "$ROOT/.env" "$ROOT/.env.bak" 2>/dev/null || true   # single rolling backup
  _set_env_kv "$ROOT/.env" "$key" "$val"
  case "$key" in
    POSTGRES_PORT) _update_database_url_port "$val" ;;       # keep DATABASE_URL in sync
    BACKEND_PORT)  _set_env_kv "$ROOT/frontend/.env.local" "NEXT_PUBLIC_API_BASE_URL" "http://localhost:$val/api/v1" ;;
  esac
  cp -f "$ROOT/.env" "$ROOT/backend/.env"
  c_green "Set $key=$val (.env + backend/.env updated; previous saved to .env.bak)."
  c_warn  "Apply it now with:  ./allhaven.sh restart"
}

# -----------------------------------------------------------------------------
# Ollama helper (local, free AI). Pulls a model ONLY when you pass one.
# -----------------------------------------------------------------------------
cmd_ollama() {
  local model="${1:-}"
  if ! need ollama; then
    c_err "Ollama is not installed."
    echo "Install it from https://ollama.com/download then re-run:  ./allhaven.sh ollama llama3.2"
    exit 1
  fi
  if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    c_blue "Starting 'ollama serve' in the background…"
    nohup ollama serve >/tmp/ollama.log 2>&1 &
    sleep 2
  fi
  if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    c_green "Ollama is running at http://localhost:11434"
  else
    c_err "Ollama did not start. Check: ollama serve"
    exit 1
  fi
  if [ -n "$model" ]; then
    c_blue "Pulling model '$model' (this can take a while)…"
    ollama pull "$model"
    c_green "Model '$model' is ready."
  else
    echo "Installed models:"
    ollama list || true
    c_warn "No model name given — nothing was pulled."
    echo "To download one, e.g.:  ./allhaven.sh ollama llama3.2"
  fi
  echo
  c_blue "Next, in AllHaven → Settings → AI Providers → Ollama Local Agent → Configure:"
  echo "  Base URL:      http://localhost:11434"
  echo "  Default model: ${model:-<the model you pulled>}"
  echo "  Save → Test (should become Online) → pick it in AI Chat."
}

usage() {
  cat <<EOF
AllHaven helper (run when already installed — for a first install use ./install.sh)

  ./allhaven.sh start                Start backend + frontend + agent in the BACKGROUND
  ./allhaven.sh run                  Start in the FOREGROUND (Ctrl+C stops everything)
  ./allhaven.sh stop                 Stop backend + frontend + agent (database left running)
  ./allhaven.sh restart [target]     Restart  all (default) | backend | frontend | agent
  ./allhaven.sh status               Show what's running and on which ports
  ./allhaven.sh port [svc] [number]  Show ports, or set one (frontend|backend|postgres|agent)
  ./allhaven.sh setup                Re-run setup (.env, deps, DB migration)
  ./allhaven.sh ollama [model]       Check Ollama; optionally pull a model

Ports: backend ${BACKEND_PORT} · frontend ${FRONTEND_PORT} · postgres ${POSTGRES_PORT} · agent ${AGENT_PORT} (127.0.0.1).
After 'start'/'run', open  http://localhost:${FRONTEND_PORT}
EOF
}

case "${1:-}" in
  setup)          cmd_setup ;;
  run)            cmd_run ;;
  start)          cmd_start ;;
  stop)           cmd_stop ;;
  restart)        shift; cmd_restart "${1:-all}" ;;
  status)         cmd_status ;;
  port|ports)     shift; cmd_port "${1:-}" "${2:-}" ;;
  ollama)         shift; cmd_ollama "${1:-}" ;;
  -h|--help|help|"") usage ;;
  *) c_err "Unknown command: $1"; usage; exit 1 ;;
esac
