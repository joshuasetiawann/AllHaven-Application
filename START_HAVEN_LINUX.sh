#!/usr/bin/env bash
# =============================================================================
# Haven — one-click launcher for Linux.
#
#   First time:  double-click this file (or run ./START_HAVEN_LINUX.sh).
#                It opens the setup wizard in your browser.
#   After setup: the same click starts Haven and opens the app.
#
# Python 3 and Node.js 18+ are required; the terminal installer checks both.
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "------------------------------------------------------------"
  echo " Python 3 is required to run Haven setup."
  echo " Install it from https://www.python.org/downloads/"
  echo " (most Linux distros: 'sudo apt install python3' or 'sudo dnf install python3')"
  echo " Then run this file again."
  echo "------------------------------------------------------------"
  read -r -p "Press Enter to close… " _ || true
  exit 1
fi

# Terminal installer. First run installs & starts Haven in THIS terminal (no
# website). After setup it just starts services and opens the app.
#   HAVEN_FORCE_SETUP=1  re-run the installer even when already configured
#   HAVEN_SETUP_WEB=1    use the optional browser wizard instead
if [ "${HAVEN_SETUP_WEB:-}" = "1" ]; then
  echo "Opening the optional browser setup wizard (HAVEN_SETUP_WEB=1)…"
  exec "$PY" "$ROOT/installer/haven_setup.py"
elif [ -f "$ROOT/.env" ] && [ "${HAVEN_FORCE_SETUP:-}" != "1" ]; then
  echo "Starting Haven and opening the app…"
  exec "$PY" "$ROOT/installer/haven_launch.py"
else
  echo "Installing & starting Haven in this terminal…"
  exec "$PY" "$ROOT/installer/haven_cli.py"
fi
