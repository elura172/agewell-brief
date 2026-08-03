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

echo "🪐 [1/5] Running Biophysics Daily Ingestion Pulse..."
PYTHONPATH=. python scripts/daily_pulse.py

echo "📲 [2/5] Preparing Social Release Packages..."
PYTHONPATH=. python -m scripts.social_package --trending

echo "🎨 [3/5] Rendering 1080x1350 Prismatic Instagram Carousels..."
PYTHONPATH=. python scripts/render_instagram_carousel.py

echo "📡 [4/5] Submitting Site URLs to IndexNow Search Indexing..."
PYTHONPATH=. python scripts/run_indexnow_full_site.py

echo "🚀 [5/5] Executing Multi-Platform Social Media Handoff..."
PYTHONPATH=. python scripts/publish_social_multiplatform.py

echo "✨ Automated Daily Pulse Cycle Completed Successfully!"
