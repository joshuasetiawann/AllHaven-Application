#!/usr/bin/env bash
# =============================================================================
# Haven — one-click launcher for Linux.
#
#   First time:  double-click this file (or run ./START_HAVEN_LINUX.sh).
#                It opens the setup wizard in your browser.
#   After setup: the same click starts Haven and opens the app.
#
# Only Python 3 is required to run the wizard (everything else is guided).
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

if [ -f "$ROOT/.env" ]; then
  echo "Haven is configured — starting services and opening the app…"
  exec "$PY" "$ROOT/installer/haven_launch.py"
else
  echo "Welcome to Haven! Launching the setup wizard in your browser…"
  exec "$PY" "$ROOT/installer/haven_setup.py"
fi
