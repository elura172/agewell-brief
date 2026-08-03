import datetime as dt
import json
import os
import sys
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env variables directly
env_file = ROOT / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import agewell.pipeline

JOURNAL_FILE = ROOT / ".state/editions/journal.jsonl"
JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)

def log_journal(entry: dict):
    with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def run_pulse():
    start_time = dt.datetime.now(dt.timezone.utc)
    print(f"[{start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}] 🪐 Starting Agewell Brief Daily Ingestion Pulse...\n")

    # Step 1: Run 5-Layer Synthesis Pipeline
    try:
        agewell.pipeline.run()
    except Exception as exc:
        print(f"❌ Error during edition pipeline run: {exc}")
        sys.exit(1)

    # Step 2: Auto-publish generated posts if configured
    published_files = []
    posts_dir = ROOT / "content/posts"
    today_prefix = start_time.strftime("%Y-%m-%d")
    
    for filepath in posts_dir.glob(f"{today_prefix}-*.md"):
        content = filepath.read_text(encoding="utf-8")
        if "draft: true" in content:
            content = content.replace("draft: true", "draft: false")
            filepath.write_text(content, encoding="utf-8")
            published_files.append(filepath.name)
            print(f"  ✓ Auto-published: {filepath.name}")

    # Step 3: Run static site build
    print("\n🔨 Rebuilding static site distribution...")
    build_result = subprocess.run(["npm", "run", "build"], cwd=ROOT, capture_output=True, text=True)
    if build_result.returncode != 0:
        print(f"❌ Build failed:\n{build_result.stderr}")
        sys.exit(1)
    else:
        print("  ✓ Static build completed successfully.")

    # Step 4: Record Journal Log
    end_time = dt.datetime.now(dt.timezone.utc)
    duration = (end_time - start_time).total_seconds()
    
    journal_entry = {
        "timestamp": end_time.isoformat(),
        "date": today_prefix,
        "published_files": published_files,
        "duration_seconds": round(duration, 2),
        "status": "success"
    }
    log_journal(journal_entry)

    print(f"\n✨ Daily Ingestion Pulse completed in {duration:.1f}s!")
    print(f"📰 Total published briefs in today's edition: {len(published_files)}")

if __name__ == "__main__":
    run_pulse()
