#!/usr/bin/env bash
# AllHaven — start everything (Linux/macOS).
# Delegates to allhaven.sh, which sets up + runs the backend and frontend.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/allhaven.sh" run
