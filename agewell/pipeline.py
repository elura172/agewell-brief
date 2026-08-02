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

from openai import OpenAI


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT / "content/posts"))
STATE_FILE = Path(os.getenv("STATE_FILE", ROOT / ".state/processed.json"))
RSS_FEED_URL = os.getenv("RSS_FEED_URL", "")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "5"))


@dataclass(frozen=True)
class FeedItem:
    title: str
    summary: str
    link: str
    published: str


def clean_text(value: str | None) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def child_text(item: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(item):
        if child.tag.rsplit("}", 1)[-1] in names and child.text:
            return clean_text(child.text)
    return ""


def fetch_items(url: str) -> list[FeedItem]:
    request = urllib.request.Request(url, headers={"User-Agent": "AgewellBrief/0.1 (+rss reader)"})
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
            results.append(FeedItem(title, summary, link, published))
    return results[:MAX_ITEMS]


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


def draft(client: OpenAI, item: FeedItem, category: str) -> dict[str, Any]:
    prompt = {
        "source_title": item.title,
        "source_summary": item.summary[:5000],
        "source_url": item.link,
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
    headline = clean_text(result.get("headline")) or item.title
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
---

## {content["headline"]}

{content["dek"]}

### Three things to know

{bullets}

### Source

This brief is based on [{item.title}]({item.link}). Read the original report for full context.
{recommendation}

> **Health note:** {content["caveat"]} Consult a qualified healthcare professional for personal advice.
'''


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result[:70]


def run() -> int:
    if not RSS_FEED_URL:
        raise RuntimeError("RSS_FEED_URL is required")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    client = OpenAI()
    configured_offers = offers()

    for item in fetch_items(RSS_FEED_URL):
        key = item_id(item)
        if key in state:
            continue
        category = classify(item)
        content = draft(client, item, category)
        offer_url = configured_offers.get(category)
        target = OUTPUT_DIR / f"{dt.date.today()}-{slug(content['headline'])}-{key[:8]}.md"
        target.write_text(markdown(item, category, content, offer_url), encoding="utf-8")
        state.add(key)
        save_state(state)
        print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
