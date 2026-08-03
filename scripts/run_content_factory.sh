#!/bin/zsh
set -euo pipefail

REPO="/Users/mirrr/agewell-brief"
LOCK="/tmp/agewell-content-factory.lock"

if ! mkdir "$LOCK" 2>/dev/null; then
  exit 0
fi
trap 'rmdir "$LOCK"' EXIT

cd "$REPO"
git pull --rebase origin main
uv run --no-project --python 3.11 python -m scripts.mpt_content_runner --max-items 1 --publish
git add .state/social .state/content-records .state/video-jobs
if ! git diff --cached --quiet; then
  git config user.name "agewell-bot"
  git config user.email "actions@users.noreply.github.com"
  git commit -m "chore: publish content factory state"
  git push origin main
fi
