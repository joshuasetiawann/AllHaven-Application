#!/usr/bin/env bash
# =============================================================================
# Haven installer (Linux/macOS) — installs & starts Haven from THIS terminal.
#
# It checks for Python 3, then runs the terminal installer: checks tools, writes
# .env (with backup), pulls the database image, installs dependencies (with live
# progress), runs migrations, starts services, and opens the app. No website.
#
# Windows: run START_HAVEN_WINDOWS.bat instead.
# Prefer the optional browser wizard: HAVEN_SETUP_WEB=1 ./install.sh
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3 is required to run the AllHaven installer."
  echo "Install it from https://www.python.org/downloads/ then run ./install.sh again."
  exit 1
fi

if [ "${HAVEN_SETUP_WEB:-}" = "1" ]; then
  echo "Opening the optional browser setup wizard (HAVEN_SETUP_WEB=1)…"
  exec "$PY" "$ROOT/installer/haven_setup.py"
fi
echo "Installing & starting Haven in this terminal…"
exec "$PY" "$ROOT/installer/haven_cli.py"
