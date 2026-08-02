from __future__ import annotations

import datetime as dt
import email.utils
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


USER_AGENT = "Mozilla/5.0 (compatible; AgewellTrendRadar/1.0; +https://agewellbrief.com/about)"
STOPWORDS = {
    "about", "after", "aging", "adults", "and", "are", "could", "finds", "for", "from",
    "health", "how", "in", "may", "new", "older", "on", "study", "the", "their", "to",
    "what", "why", "with",
}


@dataclass(frozen=True)
class TrendSeed:
    name: str
    query: str
    category: str


@dataclass(frozen=True)
class TrendItem:
    title: str
    link: str
    source: str
    published: str
    seed: str
    category: str


def load_seeds(path: Path) -> list[TrendSeed]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("trend seed configuration must be a list")
    return [TrendSeed(str(item["name"]), str(item["query"]), str(item["category"])) for item in payload]


def _child(item: ET.Element, name: str) -> str:
    for node in list(item):
        if node.tag.rsplit("}", 1)[-1] == name and node.text:
            return html.unescape(node.text).strip()
    return ""


def _published(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromtimestamp(email.utils.parsedate_to_datetime(value).timestamp(), dt.timezone.utc)
    except (TypeError, ValueError, OverflowError):
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
        except ValueError:
            return None


def fetch_seed(seed: TrendSeed, limit: int = 12) -> list[TrendItem]:
    params = urllib.parse.urlencode({"q": seed.query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    url = f"https://news.google.com/rss/search?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())
    results: list[TrendItem] = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1] != "item":
            continue
        title = _child(item, "title")
        link = _child(item, "link")
        published = _child(item, "pubDate")
        if title and link:
            source = ""
            match = re.search(r"\s+-\s+([^\-]+)$", title)
            if match:
                source = match.group(1).strip()
            results.append(TrendItem(title, link, source, published, seed.name, seed.category))
    return results[:limit]


def _key(title: str) -> str:
    value = re.sub(r"\s+-\s+[^-]+$", "", title.lower())
    tokens = {
        token for token in re.findall(r"[a-z0-9]+", value)
        if len(token) > 3 and token not in STOPWORDS
    }
    return " ".join(sorted(tokens))


def _same_topic(left: str, right: str) -> bool:
    left_terms, right_terms = set(left.split()), set(right.split())
    overlap = left_terms & right_terms
    smaller = min(len(left_terms), len(right_terms))
    return len(overlap) >= 2 and smaller > 0 and len(overlap) / smaller >= 0.45


def rank_items(items: list[TrendItem], now: dt.datetime | None = None) -> list[dict[str, object]]:
    now = now or dt.datetime.now(dt.timezone.utc)
    groups: dict[str, list[TrendItem]] = defaultdict(list)
    for item in items:
        key = _key(item.title)
        matching = next((existing for existing in groups if _same_topic(key, existing)), None)
        groups[matching or key].append(item)

    ranked: list[dict[str, object]] = []
    for topic, records in groups.items():
        sources = sorted({record.source for record in records if record.source})
        dates = [_published(record.published) for record in records]
        dates = [value for value in dates if value]
        newest = max(dates) if dates else None
        age_hours = max(0.0, (now - newest).total_seconds() / 3600) if newest else 72.0
        freshness = max(0.0, 48.0 - age_hours) / 48.0
        score = round(len(records) * 4 + len(sources) * 3 + freshness * 5, 2)
        category = records[0].category
        ranked.append(
            {
                "topic": topic,
                "headline": max(records, key=lambda record: _published(record.published) or dt.datetime.min).title,
                "category": category,
                "score": score,
                "mention_count": len(records),
                "source_count": len(sources),
                "sources": sources,
                "newest": newest.isoformat() if newest else None,
                "recommendation": (
                    "Investigate now: verify against a primary or authoritative source, then draft a timely explainer."
                    if score >= 12
                    else "Watch: gather more independent coverage before drafting."
                ),
                "items": [asdict(record) for record in records],
            }
        )
    return sorted(ranked, key=lambda value: float(value["score"]), reverse=True)


def run(seed_path: Path, output_path: Path) -> int:
    seeds = load_seeds(seed_path)
    items: list[TrendItem] = []
    failures: list[dict[str, str]] = []
    for seed in seeds:
        try:
            items.extend(fetch_seed(seed))
        except Exception as exc:
            failures.append({"seed": seed.name, "error": str(exc)})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "policy": "Discovery aid only; every topic requires editorial and source review before publication.",
                "topics": rank_items(items),
                "failures": failures,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0 if items else 1


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    raise SystemExit(run(root / "config/trend-seeds.json", root / ".state/trend-radar.json"))
