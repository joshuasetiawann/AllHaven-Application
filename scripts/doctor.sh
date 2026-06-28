#!/usr/bin/env bash
# AllHaven doctor — READ-ONLY diagnostics for local setup.
# Checks tools, ports, Docker, .env, the backend venv, frontend deps, and live
# health. It changes NOTHING (no installs, no edits, no process control).
#
# Usage: ./scripts/doctor.sh
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Mirror the installer's PATH augmentation so a Node/npm installed in a common
# per-user location (not on a minimal/login PATH) isn't a false "not found".
for d in "$HOME/.local/node/bin" "$HOME/.local/bin" /usr/local/bin /opt/homebrew/bin /snap/bin \
         "$HOME/.nvm/versions/node"/*/bin "$HOME/.local/share/fnm"/*/bin; do
  [ -d "$d" ] && case ":$PATH:" in *":$d:"*) ;; *) PATH="$PATH:$d" ;; esac
done
export PATH

bold()   { printf "\033[1m%s\033[0m\n" "$1"; }
ok()     { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warnln() { printf "  \033[33m•\033[0m %s\n" "$1"; }
failln() { printf "  \033[31m✗\033[0m %s\n" "$1"; }

issues=0
note_fail() { issues=$((issues + 1)); failln "$1"; }

# --- read a key from .env (no secrets are printed by this script) ---
env_get() {
  local key="$1" def="${2:-}"
  if [ -f "$ROOT/.env" ]; then
    local val
    val="$(grep -E "^${key}=" "$ROOT/.env" | tail -n1 | cut -d= -f2- | tr -d '[:space:]')"
    [ -n "$val" ] && { printf '%s' "$val"; return; }
  fi
  printf '%s' "$def"
}

# --- port check: prefer ss, then lsof, then /dev/tcp; report the holder if we can ---
port_busy() {  # returns 0 (busy) / 1 (free)
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${port}\$" && return 0 || return 1
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 && return 0 || return 1
  else
    (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null && return 0 || return 1
  fi
}

port_holder() {  # best-effort, may be empty
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | awk -v p=":${port}" '$4 ~ p {print $6}' | head -n1
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN -Fc 2>/dev/null | grep '^c' | head -n1 | sed 's/^c/process /'
  fi
}

FE_PORT="$(env_get FRONTEND_PORT 3000)"
BE_PORT="$(env_get BACKEND_PORT 8000)"
PG_PORT="$(env_get POSTGRES_PORT 5432)"

bold "AllHaven doctor — $ROOT"

# 1) Tools
bold "Tools"
for t in python3 node npm curl; do
  if command -v "$t" >/dev/null 2>&1; then ok "$t ($("$t" --version 2>&1 | head -n1))"; else note_fail "$t not found"; fi
done
if command -v docker >/dev/null 2>&1; then
  if docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
    ok "docker daemon running ($(docker version --format '{{.Server.Version}}' 2>/dev/null))"
  else
    warnln "docker installed but the daemon isn't running (a native PostgreSQL is fine without it)"
  fi
else
  warnln "docker not found (OK if you run a native PostgreSQL on :$PG_PORT)"
fi

# 2) Ports
bold "Ports"
for entry in "postgres:$PG_PORT" "backend:$BE_PORT" "frontend:$FE_PORT"; do
  name="${entry%%:*}"; port="${entry##*:}"
  if port_busy "$port"; then
    holder="$(port_holder "$port")"
    # For postgres, "busy" is GOOD (a server is there); for backend/frontend it
    # just means the service is already running.
    ok "$name :$port in use${holder:+ — $holder}"
  else
    if [ "$name" = "postgres" ]; then
      warnln "$name :$port free — no database listening yet"
    else
      ok "$name :$port free (will be used when started)"
    fi
  fi
done

# 3) Environment files
bold "Environment"
[ -f "$ROOT/.env" ] && ok ".env present" || note_fail ".env missing — run ./install.sh"
[ -f "$ROOT/backend/.env" ] && ok "backend/.env present" || warnln "backend/.env missing (mirrored on next run)"
[ -f "$ROOT/frontend/.env.local" ] && ok "frontend/.env.local present" || warnln "frontend/.env.local missing (created on next run)"

# 4) Backend virtualenv
bold "Backend virtualenv"
VENV_PY="$ROOT/backend/.venv/bin/python"
[ -x "$VENV_PY" ] || VENV_PY="$ROOT/backend/.venv/Scripts/python.exe"
if [ -x "$VENV_PY" ]; then
  if "$VENV_PY" -c "import sys" >/dev/null 2>&1; then
    if "$VENV_PY" -c "import fastapi, alembic" >/dev/null 2>&1; then
      ok "venv valid — fastapi & alembic import ($("$VENV_PY" --version 2>&1))"
    else
      note_fail "venv exists but dependencies don't import — run ./install.sh (it repairs/installs)"
    fi
  else
    note_fail "venv Python won't run (broken) — ./install.sh moves it aside and rebuilds"
  fi
  ALEMBIC="$ROOT/backend/.venv/bin/alembic"; [ -x "$ALEMBIC" ] || ALEMBIC="$ROOT/backend/.venv/Scripts/alembic.exe"
  [ -x "$ALEMBIC" ] && ok "venv alembic console script present" || warnln "venv alembic script missing (installed with deps)"
else
  note_fail "backend/.venv missing — run ./install.sh"
fi

# 5) Frontend deps
bold "Frontend"
[ -d "$ROOT/frontend/node_modules" ] && ok "frontend/node_modules present" || note_fail "node_modules missing — run ./install.sh (npm install)"

# 6) Live health (only meaningful if services are running)
bold "Live health"
if code=$(curl -s -o /dev/null -m 5 -w "%{http_code}" "http://localhost:${BE_PORT}/api/v1/health" 2>/dev/null) && [ "$code" = "200" ]; then
  ok "backend /api/v1/health → 200"
else
  warnln "backend not responding on :$BE_PORT (start it: ./allhaven.sh run)"
fi
if code=$(curl -s -o /dev/null -m 5 -w "%{http_code}" "http://localhost:${FE_PORT}" 2>/dev/null) && [ "$code" = "200" ]; then
  ok "frontend → 200"
else
  warnln "frontend not responding on :$FE_PORT (start it: ./allhaven.sh run)"
fi

echo
if [ "$issues" -eq 0 ]; then
  bold "No blocking issues found."
  exit 0
else
  bold "$issues issue(s) need attention — see ✗ lines above. './install.sh' is safe to re-run (idempotent)."
  exit 1
fi
