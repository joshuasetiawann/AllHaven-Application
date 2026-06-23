#!/usr/bin/env bash
# =============================================================================
# AllHaven Command Center — one-command setup & run helper
#
# Usage (run from the repo root, i.e. the CORE-OS-APPLICATION folder):
#   ./allhaven.sh setup      # one-time: env + secrets + deps + DB migration
#   ./allhaven.sh run        # start PostgreSQL + backend + frontend (dev)
#   ./allhaven.sh ollama [model]
#                          # check local Ollama; optionally pull a model
#   ./allhaven.sh stop       # stop background servers started by this script
#
# Quick start:  ./allhaven.sh run   (it runs setup automatically if needed)
# Then open:    http://localhost:3000   (use localhost, not 127.0.0.1)
#
# Safe by design: never prints/commits secrets, never deletes Docker volumes,
# never pulls Ollama models unless you explicitly ask via `ollama <model>`.
# =============================================================================

set -euo pipefail

# Resolve repo root (the directory containing this script).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
AGENT_PORT="${HAVEN_AGENT_PORT:-8765}"   # local control agent (System Control panel)
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
# PostgreSQL (Docker preferred; otherwise assume a local server on 5432)
# -----------------------------------------------------------------------------
ensure_postgres() {
  if need docker && docker compose version >/dev/null 2>&1; then
    c_blue "Starting PostgreSQL via Docker Compose…"
    docker compose up -d postgres
    # Wait until it accepts connections.
    for _ in $(seq 1 30); do
      if docker compose exec -T postgres pg_isready -U allhaven -d allhaven >/dev/null 2>&1; then
        c_green "PostgreSQL is ready."; return 0
      fi
      sleep 1
    done
    c_warn "PostgreSQL did not report ready in time; continuing anyway."
  else
    c_warn "Docker not found. Assuming a local PostgreSQL is running on :5432"
    c_warn "with user/pass/db = allhaven/allhaven/allhaven (see .env to change)."
  fi
}

# -----------------------------------------------------------------------------
# Backend: venv + deps + migration
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

# -----------------------------------------------------------------------------
# Frontend: npm install
# -----------------------------------------------------------------------------
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
  c_green "Setup complete. Run:  ./allhaven.sh run"
}

# -----------------------------------------------------------------------------
# Run both servers (backend in background, frontend in foreground)
# -----------------------------------------------------------------------------
cmd_run() {
  require_tools
  ensure_env
  ensure_postgres
  # Make sure deps + migration are in place.
  [ -d "$ROOT/backend/.venv" ] || setup_backend
  [ -d "$ROOT/frontend/node_modules" ] || setup_frontend

  mkdir -p "$PID_DIR"

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
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  c_green "Backend up. Open the app at:  http://localhost:${FRONTEND_PORT}"
  if [ -n "$LAN_IP" ]; then
    c_green "On other devices (same Wi-Fi):  http://${LAN_IP}:${FRONTEND_PORT}"
    c_warn  "The API base auto-follows the host, so phones/tablets just work — no rebuild."
  fi
  c_warn  "Tip: use http://localhost (not 127.0.0.1) on this machine."
  c_blue "Starting frontend (dev, reachable on your LAN)… press Ctrl+C to stop everything."
  cd "$ROOT/frontend"
  # -H 0.0.0.0 makes the dev server reachable from other devices on the network.
  npm run dev -- -H 0.0.0.0 -p "${FRONTEND_PORT}"
}

# -----------------------------------------------------------------------------
# Background start / stop / restart (both backend + frontend, + control agent)
# -----------------------------------------------------------------------------
# Each service runs in its own session (setsid) so we can kill the whole process
# group — important for the frontend, where `npm` spawns a `next-server` child.
_start_bg() {  # _start_bg <name> <command...>
  local name="$1"; shift
  mkdir -p "$PID_DIR" "$LOG_DIR"
  if _is_running "$name"; then c_warn "$name already running (pid $(cat "$PID_DIR/$name.pid"))."; return 0; fi
  setsid "$@" >"$LOG_DIR/$name.log" 2>&1 < /dev/null &
  echo $! > "$PID_DIR/$name.pid"
  c_green "$name started (pid $!) — logs: $LOG_DIR/$name.log"
}

_is_running() {  # _is_running <name>
  local f="$PID_DIR/$1.pid"
  [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null
}

_stop_one() {  # _stop_one <name>
  local name="$1" f="$PID_DIR/$name.pid" pid
  if [ ! -f "$f" ]; then c_warn "$name not tracked (no pid)."; return 0; fi
  pid="$(cat "$f" 2>/dev/null || true)"
  # Only signal a numeric pid that is still alive — guards against a corrupt pid
  # file and against PID reuse signalling an unrelated process group.
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true   # kill the whole group, then fall back
    c_green "$name stopped."
  else
    c_warn "$name was not running (cleaned stale pid)."
  fi
  rm -f "$f"
}

start_agent_bg() {  # local control agent for the in-app System Control panel (127.0.0.1 only)
  [ -x "$VENV_PY" ] || return 0   # best-effort; agent needs the backend venv
  _start_bg agent "$VENV_PY" "$ROOT/installer/haven_agent.py"
}

cmd_start() {  # background: backend + frontend + agent (does setup if needed)
  require_tools; ensure_env; ensure_postgres
  [ -d "$ROOT/backend/.venv" ] || setup_backend
  [ -d "$ROOT/frontend/node_modules" ] || setup_frontend
  _start_bg backend bash -c "cd '$ROOT/backend' && source .venv/bin/activate && alembic upgrade head >/dev/null 2>&1 && exec uvicorn app.main:app --host 0.0.0.0 --port '$BACKEND_PORT'"
  start_agent_bg
  sleep 2
  _start_bg frontend bash -c "cd '$ROOT/frontend' && exec npm run dev -- -H 0.0.0.0 -p '$FRONTEND_PORT'"
  local lan; lan="$(hostname -I 2>/dev/null | awk '{print $1}')"
  c_green "All services starting in the background. Open:  http://localhost:${FRONTEND_PORT}"
  [ -n "$lan" ] && c_green "On the LAN / phone (same Wi-Fi):  http://${lan}:${FRONTEND_PORT}"
  c_blue "Stop with:  ./allhaven.sh stop    ·    Restart with:  ./allhaven.sh restart"
}

cmd_stop() {  # stop everything this script started
  _stop_one frontend
  _stop_one backend
  _stop_one agent
}

cmd_restart() {  # restart both servers (and the agent) — picks up code/.env changes
  c_blue "Restarting AllHaven (backend + frontend + agent)…"
  cmd_stop
  sleep 1
  cmd_start
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
  # Ensure the server is up.
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

  ./allhaven.sh run             Start backend + frontend (foreground; Ctrl+C stops all)
  ./allhaven.sh start           Start backend + frontend + agent in the BACKGROUND
  ./allhaven.sh restart         Restart backend + frontend + agent (picks up changes)
  ./allhaven.sh stop            Stop everything started in the background
  ./allhaven.sh setup           Re-run setup (.env, deps, DB migration)
  ./allhaven.sh ollama [model]  Check Ollama; optionally pull a model

Ports: backend ${BACKEND_PORT} · frontend ${FRONTEND_PORT} · agent ${AGENT_PORT} (127.0.0.1).
Open http://localhost:${FRONTEND_PORT} after 'run'/'start'.
EOF
}

case "${1:-run}" in
  setup)        cmd_setup ;;
  run)          cmd_run ;;
  start)        cmd_start ;;
  restart)      cmd_restart ;;
  stop)         cmd_stop ;;
  ollama)       shift; cmd_ollama "${1:-}" ;;
  -h|--help|help) usage ;;
  *) c_err "Unknown command: $1"; usage; exit 1 ;;
esac
