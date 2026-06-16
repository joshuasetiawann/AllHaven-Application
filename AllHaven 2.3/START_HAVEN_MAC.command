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

# Default: terminal installer (shows live Docker/pip/npm progress, then starts &
# opens the app). It is idempotent — first run installs everything, later runs just
# start. Set HAVEN_SETUP_WEB=1 to use the browser-based wizard instead.
if [ "${HAVEN_SETUP_WEB:-}" = "1" ]; then
  echo "Launching the browser setup wizard (HAVEN_SETUP_WEB=1)…"
  exec "$PY" "$ROOT/installer/haven_setup.py"
else
  echo "Starting Haven in this terminal (first run installs everything automatically)…"
  exec "$PY" "$ROOT/installer/haven_cli.py"
fi
