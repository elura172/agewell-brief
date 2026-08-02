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

from bs4 import BeautifulSoup
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
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "3"))
MAX_ITEMS_PER_FEED = int(os.getenv("MAX_ITEMS_PER_FEED", "15"))
MAX_ITEMS_PER_PUBLISHER = int(os.getenv("MAX_ITEMS_PER_PUBLISHER", "2"))
LEAD_SOURCE_CHARS = int(os.getenv("LEAD_SOURCE_CHARS", "18000"))
MIN_LEAD_SOURCE_CHARS = int(os.getenv("MIN_LEAD_SOURCE_CHARS", "2500"))
CANDIDATE_POOL_SIZE = int(os.getenv("CANDIDATE_POOL_SIZE", "9"))


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


def fetch_ranked_items(
    sources: list[FeedSource],
    processed: set[str] | None = None,
    limit: int | None = None,
) -> list[FeedItem]:
    candidates: list[FeedItem] = []
    for source in sources:
        try:
            candidates.extend(fetch_items(source))
        except Exception as exc:
            print(f"Feed failed ({source.name}): {exc}", file=sys.stderr)

    if processed:
        candidates = [item for item in candidates if item_id(item) not in processed]
    return select_ranked_items(candidates, limit)


def select_ranked_items(candidates: list[FeedItem], limit: int | None = None) -> list[FeedItem]:
    """Deduplicate and rank stories while keeping each batch source-diverse."""
    target_count = limit if limit is not None else MAX_ITEMS
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
        if len(selected) == target_count:
            return selected

    # If too few publishers have fresh stories, fill the remaining slots by score.
    for item in ranked:
        if item.link in selected_links:
            continue
        selected.append(item)
        if len(selected) == target_count:
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


def _json_ld_article_body(soup: BeautifulSoup) -> str:
    def find_body(value: Any) -> str:
        if isinstance(value, dict):
            body = value.get("articleBody")
            if isinstance(body, str):
                return clean_text(body)
            for child in value.values():
                found = find_body(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = find_body(child)
                if found:
                    return found
        return ""

    for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            found = find_body(json.loads(node.string or node.get_text()))
        except (json.JSONDecodeError, TypeError):
            continue
        if found:
            return found
    return ""


def extract_article_text(document: bytes | str) -> str:
    """Extract readable source material without retaining page chrome or markup."""
    soup = BeautifulSoup(document, "html.parser")
    structured_body = _json_ld_article_body(soup)
    if len(structured_body) >= 500:
        return structured_body[:LEAD_SOURCE_CHARS]

    for node in soup.select("script, style, nav, footer, header, aside, form, noscript, svg"):
        node.decompose()
    container = soup.find("article") or soup.find("main") or soup.select_one('[role="main"]') or soup.body
    if container is None:
        return ""

    chunks: list[str] = []
    for node in container.select("h2, h3, p, li"):
        text = clean_text(node.get_text(" ", strip=True))
        if len(text) < 25 or text in chunks[-3:]:
            continue
        chunks.append(text)
    return "\n".join(chunks)[:LEAD_SOURCE_CHARS]


def fetch_article_text(item: FeedItem) -> str:
    """Fetch lead-story source material, falling back safely to the RSS summary."""
    request = urllib.request.Request(
        item.link,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AgewellBrief/0.3; editorial research)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            extracted = extract_article_text(response.read())
    except Exception as exc:
        print(f"Source page failed ({item.source_name}): {exc}", file=sys.stderr)
        extracted = ""
    return extracted if len(extracted) >= 500 else item.summary


def choose_edition(candidates: list[FeedItem]) -> list[tuple[FeedItem, str, str | None]]:
    """Choose a source-rich lead and the two strongest remaining signals."""
    if not candidates:
        return []

    lead = candidates[0]
    lead_source = fetch_article_text(lead)
    for candidate in candidates:
        source_text = lead_source if candidate is lead else fetch_article_text(candidate)
        if len(source_text) >= MIN_LEAD_SOURCE_CHARS:
            lead = candidate
            lead_source = source_text
            break

    signals = [candidate for candidate in candidates if candidate.link != lead.link][: max(0, MAX_ITEMS - 1)]
    return [(lead, "lead", lead_source)] + [(signal, "signal", None) for signal in signals]


def classify(item: FeedItem) -> str:
    text = f"{item.title} {item.summary}".lower()
    rules = {
        "mobility": ("joint", "arthritis", "knee", "back pain", "balance", "walking"),
        "metabolic health": ("blood sugar", "glucose", "insulin", "metabolic", "diabetes"),
        "brain health": ("memory", "cognition", "brain", "dementia", "alzheimer", "parkinson", "sleep"),
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


def draft(
    client: OpenAI,
    item: FeedItem,
    category: str,
    content_type: str = "signal",
    source_text: str | None = None,
) -> dict[str, Any]:
    is_lead = content_type == "lead"
    source_material = source_text or item.summary
    source_is_deep = len(source_material) >= MIN_LEAD_SOURCE_CHARS
    minimum_lead_words = 500 if source_is_deep else 300
    prompt: dict[str, Any] = {
        "source_title": item.title,
        "source_summary": item.summary[:5000],
        "source_material": source_material[:LEAD_SOURCE_CHARS] if is_lead else item.summary[:5000],
        "source_url": item.link,
        "source_name": item.source_name,
        "category": category,
        "content_type": content_type,
        "requirements": [
            "Write clear, engaging health journalism for readers over 50.",
            "Use only claims supported by the supplied source material.",
            "Do not diagnose, prescribe, promise results, or invent institutions or studies.",
            "Do not imply that a supplement treats or cures a disease.",
            "Write with tension, specificity, agency, and warmth; avoid hype and filler.",
            "bullets must contain exactly three items, each at most 20 words.",
        ],
    }
    if is_lead:
        prompt["requirements"].extend(
            [
                (
                    "Create an original 600-900 word analysis based only on source_material."
                    if source_is_deep
                    else "Create a focused 350-500 word analysis; do not pad beyond the limited source material."
                ),
                "Return JSON with headline, dek, sections, bullets, and caveat.",
                "sections must contain exactly four objects with heading and paragraphs fields.",
                "Each paragraphs field must be an array of two or three complete paragraphs.",
                "The four sections should explain why this matters, what was found, how to interpret it, and practical next steps.",
                "Separate reported evidence from interpretation and clearly state uncertainty.",
            ]
        )
    else:
        prompt["requirements"].extend(
            [
                "Create a compact news signal under 140 words.",
                "Return JSON with headline, dek, bullets, and caveat.",
            ]
        )
    messages = [
        {
            "role": "system",
            "content": "You are a careful health-news editor. Be vivid and useful, but never exaggerate evidence.",
        },
        {"role": "user", "content": json.dumps(prompt)},
    ]
    result: dict[str, Any] | None = None
    draft_error: Exception | None = None
    for _attempt in range(2):
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            max_tokens=3200 if is_lead else 1400,
            response_format={"type": "json_object"},
            messages=messages,
            extra_body={"thinking": {"type": "disabled"}},
        )
        try:
            candidate = json.loads(response.choices[0].message.content or "{}")
            if is_lead:
                raw_sections = candidate.get("sections")
                if not isinstance(raw_sections, list) or len(raw_sections) != 4:
                    raise ValueError("lead draft requires four sections")
                lead_words = len(
                    " ".join(
                        str(paragraph)
                        for section in raw_sections
                        if isinstance(section, dict)
                        for paragraph in section.get("paragraphs", [])
                    ).split()
                )
                if lead_words < minimum_lead_words:
                    raise ValueError(f"lead draft is too short ({lead_words} words)")
            result = candidate
            break
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            draft_error = exc
    if result is None:
        raise RuntimeError("DeepSeek returned an invalid draft twice") from draft_error
    generated_headline = clean_text(result.get("headline")) or item.title
    headline = item.title if item.headline_mode == "preserve" else generated_headline
    dek = clean_text(result.get("dek")) or item.summary
    bullets = result.get("bullets")
    if not isinstance(bullets, list) or len(bullets) != 3:
        bullets = ["The source reports a new health-related finding.", "The result needs context before changing routines.", "Discuss personal decisions with a qualified clinician."]
    caveat = clean_text(result.get("caveat")) or "This brief is informational and is not medical advice."
    sections: list[dict[str, Any]] = []
    if is_lead:
        raw_sections = result.get("sections")
        if not isinstance(raw_sections, list) or len(raw_sections) != 4:
            raise RuntimeError("DeepSeek lead draft did not contain four sections")
        for section in raw_sections:
            if not isinstance(section, dict):
                raise RuntimeError("DeepSeek lead section was not an object")
            heading = clean_text(str(section.get("heading", "")))
            paragraphs = section.get("paragraphs")
            if not heading or not isinstance(paragraphs, list) or not paragraphs:
                raise RuntimeError("DeepSeek lead section was incomplete")
            sections.append(
                {
                    "heading": heading,
                    "paragraphs": [clean_text(str(paragraph)) for paragraph in paragraphs if clean_text(str(paragraph))],
                }
            )
    return {
        "headline": headline,
        "dek": dek,
        "bullets": [clean_text(str(x)) for x in bullets],
        "caveat": caveat,
        "sections": sections,
    }


def quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def markdown(
    item: FeedItem,
    category: str,
    content: dict[str, Any],
    offer_url: str | None,
    content_type: str = "signal",
    edition_rank: int = 1,
    edition_time: dt.datetime | None = None,
) -> str:
    published_at = edition_time or dt.datetime.now(dt.timezone.utc)
    bullets = "\n".join(f"- {bullet}" for bullet in content["bullets"])
    sections = ""
    if content_type == "lead":
        sections = "\n\n".join(
            f"## {section['heading']}\n\n" + "\n\n".join(section["paragraphs"])
            for section in content.get("sections", [])
        )
    recommendation = ""
    if offer_url:
        recommendation = (
            "\n\n> **Affiliate disclosure:** This optional recommendation may earn us a commission. "
            f"[View the related resource]({offer_url})."
        )
    health_note = content["caveat"]
    if not any(term in health_note.lower() for term in ("consult", "talk with", "speak with", "ask your")):
        health_note += " Consult a qualified healthcare professional for personal advice."
    return f'''---
title: "{quote(content["headline"])}"
date: {published_at.isoformat()}
draft: true
category: "{quote(category)}"
content_type: "{content_type}"
edition_rank: {edition_rank}
edition_id: "{published_at.date().isoformat()}"
source_url: "{quote(item.link)}"
source_title: "{quote(item.title)}"
source_name: "{quote(item.source_name)}"
---

{content["dek"]}

{sections}

## Three things to remember

{bullets}

### Source

This {"analysis" if content_type == "lead" else "signal"} is based on [{item.title}]({item.link}) from {item.source_name}. Read the original report for full context.
{recommendation}

> **Health note:** {health_note}
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

    edition_time = dt.datetime.now(dt.timezone.utc)
    candidates = fetch_ranked_items(sources, state, max(MAX_ITEMS, CANDIDATE_POOL_SIZE))
    for index, (item, content_type, source_text) in enumerate(choose_edition(candidates)):
        key = item_id(item)
        category = classify(item)
        content = draft(client, item, category, content_type, source_text)
        offer_url = None
        if content_type == "lead":
            offer_url = tracked_offer_url(select_offer(configured_offers, category), category, key)
        target = OUTPUT_DIR / f"{dt.date.today()}-{slug(content['headline'])}-{key[:8]}.md"
        target.write_text(
            markdown(item, category, content, offer_url, content_type, index + 1, edition_time),
            encoding="utf-8",
        )
        state.add(key)
        save_state(state)
        print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
