#!/usr/bin/env bash
# =============================================================================
# Haven installer (Linux/macOS) — a thin BOOTSTRAPPER.
#
# It only checks for Python 3, then opens the browser-based **Setup Wizard**,
# where ALL configuration happens (OS/Docker checks, ports, .env, starting
# services, health, desktop shortcut, open app). The terminal is not where you
# configure Haven — the wizard is.
#
# Windows: run START_HAVEN_WINDOWS.bat instead.
# Prefer a terminal-only install: HAVEN_SETUP_CLI=1 ./install.sh
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3 is required to bootstrap the Haven Setup Wizard."
  echo "Install it from https://www.python.org/downloads/ then run ./install.sh again."
  exit 1
fi

if [ "${HAVEN_SETUP_CLI:-}" = "1" ]; then
  exec "$PY" "$ROOT/installer/haven_cli.py"
fi
echo "Opening the Haven Setup Wizard in your browser…"
echo "(Keep this terminal open while you complete setup; you can close it afterward.)"
exec "$PY" "$ROOT/installer/haven_setup.py"
