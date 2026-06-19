#!/usr/bin/env bash
# AllHaven — stop the backend (and tell you how the frontend stops).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/allhaven.sh" stop
