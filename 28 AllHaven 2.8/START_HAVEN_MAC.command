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
