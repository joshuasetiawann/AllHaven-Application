#!/usr/bin/env bash
# =============================================================================
# Haven — one-click launcher for macOS.
#
#   First time:  double-click this file in Finder. It opens the setup wizard
#                in your browser. (macOS runs .command files in Terminal.)
#   After setup: the same double-click starts Haven and opens the app.
#
# Only Python 3 is required to run the wizard.
# If macOS blocks it the first time: right-click → Open, or
#   System Settings → Privacy & Security → "Open Anyway".
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
  echo " Install it from https://www.python.org/downloads/ (or 'brew install python')"
  echo " Then double-click this file again."
  echo "------------------------------------------------------------"
  read -r -p "Press Enter to close… " _ || true
  exit 1
fi

# Bootstrapper only. First run (no .env) opens the browser Setup Wizard, where
# ALL configuration happens; after setup it starts services and opens the app.
#   HAVEN_FORCE_WIZARD=1  re-open the wizard even when already configured
#   HAVEN_SETUP_CLI=1     use the terminal installer instead of the browser
if [ "${HAVEN_SETUP_CLI:-}" = "1" ]; then
  echo "Running the terminal installer (HAVEN_SETUP_CLI=1)…"
  exec "$PY" "$ROOT/installer/haven_cli.py"
elif [ "${HAVEN_FORCE_WIZARD:-}" = "1" ] || [ ! -f "$ROOT/.env" ]; then
  echo "Opening the Haven Setup Wizard in your browser…"
  exec "$PY" "$ROOT/installer/haven_setup.py"
else
  echo "Starting Haven and opening the app…"
  exec "$PY" "$ROOT/installer/haven_launch.py"
fi
