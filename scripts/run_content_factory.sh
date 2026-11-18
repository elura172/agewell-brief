#!/bin/zsh
set -euo pipefail

REPO="/Users/mirrr/agewell-brief"
LOCK="/tmp/agewell-content-factory.lock"
UV_BIN="/Library/Frameworks/Python.framework/Versions/3.13/bin/uv"
MPT_CONFIG="/Users/mirrr/MoneyPrinterTurbo/config.toml"

# ARCHIVED 2026-11-18: this job submits videos/posts to upload-post.com, which is
# disabled until further notice. Set UPLOAD_POST_ARCHIVED=0 to re-enable.
if [[ "${UPLOAD_POST_ARCHIVED:-1}" != "0" ]]; then
  exit 0
fi

if ! mkdir "$LOCK" 2>/dev/null; then
  exit 0
fi
trap 'rmdir "$LOCK"' EXIT

if [[ ! -f "$MPT_CONFIG" ]]; then
  exit 0
fi

cd "$REPO"
git pull --rebase origin main
"$UV_BIN" run --no-project --python 3.11 python -m scripts.mpt_content_runner --max-items 1 --publish
git add .state/social .state/content-records .state/video-jobs
if ! git diff --cached --quiet; then
  git config user.name "agewell-bot"
  git config user.email "actions@users.noreply.github.com"
  git commit -m "chore: publish content factory state"
  git push origin main
fi
