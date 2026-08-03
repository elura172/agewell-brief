"""Build a static most-read manifest from Cloudflare GraphQL analytics."""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src/data/trending.json"
API_URL = "https://api.cloudflare.com/client/v4/graphql"
WINDOW_DAYS = int(os.getenv("TRENDING_WINDOW_DAYS", "7"))
LIMIT = int(os.getenv("TRENDING_LIMIT", "5"))

QUERY = """
query TrendingBriefs($zoneTag: string, $start: Time, $end: Time) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      paths: httpRequestsAdaptiveGroups(
        limit: 100
        filter: {
          datetime_geq: $start
          datetime_lt: $end
          requestSource: "eyeball"
          clientRequestPath_like: "/brief/%"
        }
      ) {
        count
        sum { visits }
        dimensions { clientRequestPath }
      }
    }
  }
}
"""


def published_slugs() -> set[str]:
    return {
        path.stem
        for path in (ROOT / "content/posts").glob("*.md")
        if "draft: true" not in path.read_text(encoding="utf-8")
    }


def request_payload() -> dict[str, object]:
    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(days=WINDOW_DAYS)
    payload = {
        "query": QUERY,
        "variables": {
            "zoneTag": os.environ["CLOUDFLARE_ZONE_ID"],
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}",
            "Content-Type": "application/json",
            "User-Agent": "AgewellBrief/1.0 (reader trends)",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def run() -> int:
    if not os.getenv("CLOUDFLARE_API_TOKEN") or not os.getenv("CLOUDFLARE_ZONE_ID"):
        print("Cloudflare trending skipped: CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID are required.")
        return 0

    response = request_payload()
    if response.get("errors"):
        raise RuntimeError(f"Cloudflare GraphQL error: {response['errors']}")

    rows: dict[str, dict[str, int | str]] = {}
    valid_slugs = published_slugs()
    zones = response.get("data", {}).get("viewer", {}).get("zones", [])
    for zone in zones:
        for row in zone.get("paths", []):
            path = str(row.get("dimensions", {}).get("clientRequestPath", ""))
            slug = path.strip("/").split("/")[-1]
            if slug not in valid_slugs:
                continue
            visits = int((row.get("sum") or {}).get("visits") or 0)
            requests = int(row.get("count") or 0)
            current = rows.get(slug)
            if current is None or visits > int(current["visits"]):
                rows[slug] = {"slug": slug, "visits": visits, "requests": requests}

    articles = sorted(rows.values(), key=lambda row: (-int(row["visits"]), str(row["slug"])))[:LIMIT]
    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "window_days": WINDOW_DAYS,
        "source": "Cloudflare GraphQL Analytics",
        "articles": articles,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(articles)} trending briefs to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
