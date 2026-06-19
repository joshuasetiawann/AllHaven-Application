#!/usr/bin/env bash
# AllHaven health check — backend, frontend, database, and basic integration probe.
# Usage: scripts/healthcheck.sh   (override ports/hosts via env vars below)
set -uo pipefail

API_BASE="${API_BASE:-http://localhost:8000/api/v1}"
WEB_URL="${WEB_URL:-http://localhost:3000}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

green() { printf "\033[32m[OK]\033[0m %s\n" "$1"; }
red()   { printf "\033[31m[FAIL]\033[0m %s\n" "$1"; }
yellow(){ printf "\033[33m[..]\033[0m %s\n" "$1"; }

fails=0

# --- Backend ---
if code=$(curl -s -o /dev/null -m 5 -w "%{http_code}" "$API_BASE/health" 2>/dev/null) && [ "$code" = "200" ]; then
  green "Backend API reachable ($API_BASE/health → 200)"
else
  red "Backend API NOT reachable ($API_BASE/health → ${code:-no response})"; fails=$((fails+1))
fi

# --- Frontend ---
if code=$(curl -s -o /dev/null -m 5 -w "%{http_code}" "$WEB_URL" 2>/dev/null) && [ "$code" = "200" ]; then
  green "Frontend reachable ($WEB_URL → 200)"
else
  red "Frontend NOT reachable ($WEB_URL → ${code:-no response})"; fails=$((fails+1))
fi

# --- Database (TCP reachability) ---
if (echo > "/dev/tcp/$DB_HOST/$DB_PORT") 2>/dev/null; then
  green "Database port reachable ($DB_HOST:$DB_PORT)"
else
  red "Database port NOT reachable ($DB_HOST:$DB_PORT)"; fails=$((fails+1))
fi

# --- Integrations (basic note) ---
yellow "Integration/provider status (Ollama, Supabase, AI keys, …) is shown per-card"
yellow "in the web app: Settings → Connected Tools / AI Providers (login required)."

echo
if [ "$fails" -eq 0 ]; then
  green "All core services healthy."
  exit 0
else
  red "$fails core check(s) failed — see above."
  exit 1
fi
