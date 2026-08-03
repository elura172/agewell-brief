#!/bin/zsh
set -euo pipefail

REPO="/Users/mirrr/agewell-brief"
LOCK="/tmp/agewell-daily-pulse.lock"

if ! mkdir "$LOCK" 2>/dev/null; then
  echo "Daily pulse is already running. Exiting."
  exit 0
fi
trap 'rmdir "$LOCK"' EXIT

cd "$REPO"
source venv/bin/activate
PYTHONPATH=. python scripts/daily_pulse.py
