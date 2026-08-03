"""Build a lightweight operating scorecard from locally available signals."""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path, fallback: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def main() -> int:
    posts = [p for p in (ROOT / "content/posts").glob("*.md") if "draft: true" not in p.read_text(encoding="utf-8")]
    trends = read(ROOT / "src/data/trending.json", {})
    manifest = read(ROOT / ".state/social/manifest.json", {})
    clickbank = read(ROOT / ".state/clickbank-analytics.json", {})
    articles = manifest.get("articles", {}) if isinstance(manifest, dict) else {}
    social_counts = Counter()
    for article in articles.values():
        for platform, state in article.get("platforms", {}).items():
            social_counts[f"{platform}:{state.get('status', 'pending')}"] += 1
    top = trends.get("articles", []) if isinstance(trends, dict) else []
    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "window": "current Cloudflare trend window",
        "available_metrics": {
            "published_articles": len(posts),
            "top_articles": top[:5],
            "social_status_counts": dict(sorted(social_counts.items())),
            "clickbank_status": clickbank.get("status", "missing") if isinstance(clickbank, dict) else "missing",
            "clickbank_error": clickbank.get("error") if isinstance(clickbank, dict) else None,
        },
        "not_yet_connected": [
            "Facebook reach and video-platform views APIs",
            "first-party outbound affiliate click events",
            "multi-day historical trend series",
        ],
    }
    target = ROOT / ".state/scorecard.json"
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote scorecard to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
