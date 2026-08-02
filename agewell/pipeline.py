from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from openai import OpenAI


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT / "content/posts"))
STATE_FILE = Path(os.getenv("STATE_FILE", ROOT / ".state/processed.json"))
RSS_FEED_URL = os.getenv("RSS_FEED_URL", "")
RSS_FEEDS_JSON = os.getenv("RSS_FEEDS_JSON", "")
FEED_CONFIG_FILE = Path(os.getenv("FEED_CONFIG_FILE", ROOT / "config/feed-portfolio.json"))
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "5"))
MAX_ITEMS_PER_FEED = int(os.getenv("MAX_ITEMS_PER_FEED", "15"))
MAX_ITEMS_PER_PUBLISHER = int(os.getenv("MAX_ITEMS_PER_PUBLISHER", "2"))


@dataclass(frozen=True)
class FeedSource:
    name: str
    url: str
    priority: int = 0
    headline_mode: str = "rewrite"
    publisher: str = ""


@dataclass(frozen=True)
class FeedItem:
    title: str
    summary: str
    link: str
    published: str
    source_name: str = "Unknown source"
    source_priority: int = 0
    headline_mode: str = "rewrite"
    source_group: str = "Unknown source"


def clean_text(value: str | None) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def child_text(item: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(item):
        if child.tag.rsplit("}", 1)[-1] in names and child.text:
            return clean_text(child.text)
    return ""


def feed_sources() -> list[FeedSource]:
    raw_config = RSS_FEEDS_JSON
    if not raw_config and FEED_CONFIG_FILE.exists():
        raw_config = FEED_CONFIG_FILE.read_text(encoding="utf-8")
    if raw_config:
        try:
            payload = json.loads(raw_config)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Feed portfolio must be valid JSON") from exc
        if not isinstance(payload, list):
            raise RuntimeError("RSS_FEEDS_JSON must contain a list of feed objects")
        sources: list[FeedSource] = []
        for value in payload:
            if not isinstance(value, dict) or not value.get("name") or not value.get("url"):
                raise RuntimeError("Each RSS_FEEDS_JSON entry requires name and url")
            mode = str(value.get("headline_mode", "rewrite"))
            if mode not in {"rewrite", "preserve"}:
                raise RuntimeError("headline_mode must be rewrite or preserve")
            sources.append(
                FeedSource(
                    name=str(value["name"]),
                    url=str(value["url"]),
                    priority=int(value.get("priority", 0)),
                    headline_mode=mode,
                    publisher=str(value.get("publisher", "")),
                )
            )
        return sources
    if RSS_FEED_URL:
        return [FeedSource("Primary feed", RSS_FEED_URL)]
    return []


def fetch_items(source: FeedSource) -> list[FeedItem]:
    request = urllib.request.Request(source.url, headers={"User-Agent": "AgewellBrief/0.2 (+rss reader)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())

    entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] in {"item", "entry"}]
    results: list[FeedItem] = []
    for item in entries:
        link = child_text(item, ("link",))
        if not link:
            for node in list(item):
                if node.tag.rsplit("}", 1)[-1] == "link" and node.attrib.get("href"):
                    link = node.attrib["href"]
                    break
        title = child_text(item, ("title",))
        summary = child_text(item, ("description", "summary", "content"))
        published = child_text(item, ("pubDate", "published", "updated"))
        if title and link:
            results.append(
                FeedItem(
                    title,
                    summary,
                    link,
                    published,
                    source.name,
                    source.priority,
                    source.headline_mode,
                    source.publisher or source.name,
                )
            )
    return results[:MAX_ITEMS_PER_FEED]


def normalized_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def relevance_score(item: FeedItem) -> int:
    text = f"{item.title} {item.summary}".lower()
    score = item.source_priority
    weighted_terms = {
        6: ("aging", "ageing", "over 50", "older adults", "seniors", "longevity", "healthspan"),
        5: ("memory", "dementia", "alzheimer", "mobility", "balance", "muscle", "sleep"),
        4: ("blood sugar", "diabetes", "heart", "walking", "exercise", "nutrition", "supplement"),
        3: ("warning", "fraud", "scam", "recall", "breakthrough", "surprising", "linked to"),
    }
    for weight, terms in weighted_terms.items():
        score += sum(weight for term in terms if term in text)
    if classify(item) != "general wellness":
        score += 4
    if any(term in text for term in ("grant", "appoints", "director named", "funding opportunity", "webinar")):
        score -= 10
    return score


def fetch_ranked_items(sources: list[FeedSource]) -> list[FeedItem]:
    candidates: list[FeedItem] = []
    for source in sources:
        try:
            candidates.extend(fetch_items(source))
        except Exception as exc:
            print(f"Feed failed ({source.name}): {exc}", file=sys.stderr)

    return select_ranked_items(candidates)


def select_ranked_items(candidates: list[FeedItem]) -> list[FeedItem]:
    """Deduplicate and rank stories while keeping each batch source-diverse."""
    best_by_title: dict[str, FeedItem] = {}
    for item in candidates:
        key = normalized_title(item.title)
        current = best_by_title.get(key)
        if current is None or relevance_score(item) > relevance_score(current):
            best_by_title[key] = item

    ranked = sorted(best_by_title.values(), key=relevance_score, reverse=True)
    selected: list[FeedItem] = []
    selected_links: set[str] = set()
    publisher_counts: dict[str, int] = {}
    publisher_cap = max(1, MAX_ITEMS_PER_PUBLISHER)

    for item in ranked:
        publisher = item.source_group or item.source_name
        if publisher_counts.get(publisher, 0) >= publisher_cap:
            continue
        selected.append(item)
        selected_links.add(item.link)
        publisher_counts[publisher] = publisher_counts.get(publisher, 0) + 1
        if len(selected) == MAX_ITEMS:
            return selected

    # If too few publishers have fresh stories, fill the remaining slots by score.
    for item in ranked:
        if item.link in selected_links:
            continue
        selected.append(item)
        if len(selected) == MAX_ITEMS:
            break
    return selected


def item_id(item: FeedItem) -> str:
    return hashlib.sha256(item.link.encode("utf-8")).hexdigest()[:24]


def load_state() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return set()


def save_state(state: set[str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(sorted(state), indent=2) + "\n", encoding="utf-8")


def classify(item: FeedItem) -> str:
    text = f"{item.title} {item.summary}".lower()
    rules = {
        "mobility": ("joint", "arthritis", "knee", "back pain", "balance", "walking"),
        "metabolic health": ("blood sugar", "glucose", "insulin", "metabolic", "diabetes"),
        "brain health": ("memory", "cognition", "brain", "dementia", "sleep"),
        "longevity": ("aging", "ageing", "longevity", "lifespan", "healthspan"),
    }
    for category, terms in rules.items():
        if any(term in text for term in terms):
            return category
    return "general wellness"


def offers() -> dict[str, str]:
    raw = os.getenv("AFFILIATE_OFFERS_JSON", "{}")
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        print("Ignoring invalid AFFILIATE_OFFERS_JSON", file=sys.stderr)
        return {}


def select_offer(configured_offers: dict[str, str], category: str) -> str | None:
    """Use a category-specific offer when available, otherwise the evergreen fallback."""
    return configured_offers.get(category) or configured_offers.get("general wellness")


def tracked_offer_url(base_url: str | None, category: str, article_id: str) -> str | None:
    """Append a stable ClickBank TID to a validated HopLink.

    ClickBank TIDs support lowercase letters, numbers, and underscores. Keeping
    the account-generated HopLink intact preserves encryption and any selected
    seller landing page.
    """
    if not base_url:
        return None

    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".clickbank.net"):
        raise ValueError(f"Affiliate offer is not a valid HTTPS ClickBank URL: {base_url}")

    category_token = re.sub(r"[^a-z0-9_]+", "_", category.lower()).strip("_")[:32]
    article_token = re.sub(r"[^a-z0-9_]+", "", article_id.lower())[:24]
    tid = f"agewell_{category_token}_{article_token}"[:100]
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["tid"] = tid
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def draft(client: OpenAI, item: FeedItem, category: str) -> dict[str, Any]:
    prompt = {
        "source_title": item.title,
        "source_summary": item.summary[:5000],
        "source_url": item.link,
        "source_name": item.source_name,
        "category": category,
        "requirements": [
            "Write a clear, engaging news brief for older readers.",
            "Use only claims supported by the supplied title and summary.",
            "Do not diagnose, prescribe, promise results, or invent institutions or studies.",
            "Do not imply that a supplement treats or cures a disease.",
            "Return JSON with headline, dek, bullets, and caveat.",
            "bullets must contain exactly three items, each at most 20 words.",
        ],
    }
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        max_tokens=900,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You are a careful health-news editor. Be vivid and useful, but never exaggerate evidence.",
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    result = json.loads(response.choices[0].message.content or "{}")
    generated_headline = clean_text(result.get("headline")) or item.title
    headline = item.title if item.headline_mode == "preserve" else generated_headline
    dek = clean_text(result.get("dek")) or item.summary
    bullets = result.get("bullets")
    if not isinstance(bullets, list) or len(bullets) != 3:
        bullets = ["The source reports a new health-related finding.", "The result needs context before changing routines.", "Discuss personal decisions with a qualified clinician."]
    caveat = clean_text(result.get("caveat")) or "This brief is informational and is not medical advice."
    return {"headline": headline, "dek": dek, "bullets": [clean_text(str(x)) for x in bullets], "caveat": caveat}


def quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def markdown(item: FeedItem, category: str, content: dict[str, Any], offer_url: str | None) -> str:
    today = dt.datetime.now(dt.timezone.utc).isoformat()
    bullets = "\n".join(f"- {bullet}" for bullet in content["bullets"])
    recommendation = ""
    if offer_url:
        recommendation = (
            "\n\n> **Affiliate disclosure:** This optional recommendation may earn us a commission. "
            f"[View the related resource]({offer_url})."
        )
    return f'''---
title: "{quote(content["headline"])}"
date: {today}
draft: true
category: "{quote(category)}"
source_url: "{quote(item.link)}"
source_title: "{quote(item.title)}"
source_name: "{quote(item.source_name)}"
---

## {content["headline"]}

{content["dek"]}

### Three things to know

{bullets}

### Source

This brief is based on [{item.title}]({item.link}) from {item.source_name}. Read the original report for full context.
{recommendation}

> **Health note:** {content["caveat"]} Consult a qualified healthcare professional for personal advice.
'''


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result[:70]


def run() -> int:
    sources = feed_sources()
    if not sources:
        raise RuntimeError("RSS_FEEDS_JSON or RSS_FEED_URL is required")
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is required")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=LLM_BASE_URL)
    configured_offers = offers()

    for item in fetch_ranked_items(sources):
        key = item_id(item)
        if key in state:
            continue
        category = classify(item)
        content = draft(client, item, category)
        offer_url = tracked_offer_url(select_offer(configured_offers, category), category, key)
        target = OUTPUT_DIR / f"{dt.date.today()}-{slug(content['headline'])}-{key[:8]}.md"
        target.write_text(markdown(item, category, content, offer_url), encoding="utf-8")
        state.add(key)
        save_state(state)
        print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
