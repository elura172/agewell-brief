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
from html.entities import html5
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from openai import OpenAI

from agewell.edition import EditionRecorder, audit_release
from agewell.editorial import (
    AlignmentReview,
    DeferredVisionReviewer,
    EvidencePacket,
    ImageBrief,
    build_evidence_packet,
    direct_image,
    review_image_metadata,
)
from agewell.images import (
    ImageSearchCache,
    PublishedImage,
    append_image_ledger,
    load_image_creators,
    load_image_ledger,
    persist_image,
    search_image_candidates,
)


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT / "content/posts"))
STATE_FILE = Path(os.getenv("STATE_FILE", ROOT / ".state/processed.json"))
RSS_FEED_URL = os.getenv("RSS_FEED_URL", "")
RSS_FEEDS_JSON = os.getenv("RSS_FEEDS_JSON", "")
FEED_CONFIG_FILE = Path(os.getenv("FEED_CONFIG_FILE", ROOT / "config/feed-portfolio.json"))
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "3"))
MAX_ITEMS_PER_FEED = int(os.getenv("MAX_ITEMS_PER_FEED", "15"))
MAX_ITEMS_PER_PUBLISHER = int(os.getenv("MAX_ITEMS_PER_PUBLISHER", "2"))
LEAD_SOURCE_CHARS = int(os.getenv("LEAD_SOURCE_CHARS", "18000"))
MIN_LEAD_SOURCE_CHARS = int(os.getenv("MIN_LEAD_SOURCE_CHARS", "2500"))
CANDIDATE_POOL_SIZE = int(os.getenv("CANDIDATE_POOL_SIZE", "9"))
PUBLIC_ROOT = Path(os.getenv("PUBLIC_ROOT", ROOT / "public"))
EDITION_STATE_ROOT = Path(os.getenv("EDITION_STATE_ROOT", ROOT / ".state/editions"))
IMAGE_CACHE_FILE = Path(os.getenv("IMAGE_CACHE_FILE", ROOT / ".state/image-search-cache.json"))
IMAGE_LEDGER_FILE = Path(os.getenv("IMAGE_LEDGER_FILE", ROOT / ".state/image-ledger.json"))

PUBLICATION_STYLE_REQUIREMENTS = (
    "Use Agewell's publication register: clear, spirited, respectful, and concrete.",
    "Vary sentence length naturally and prefer direct verbs over inflated significance language.",
    "Remove promotional phrasing, vague attribution, filler, manufactured punchlines, and generic future-looking conclusions.",
    "Use sentence case for section headings.",
    "Do not invent facts, quotations, colour, or scenes to make the writing feel more human.",
    "Treat these as editing preferences, not a rigid template; clarity and factual nuance outrank style rules.",
)


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


def normalize_source_url(value: str) -> str:
    """Upgrade known publisher links that still arrive as legacy HTTP URLs."""
    parsed = urlsplit(value)
    if parsed.scheme == "http" and parsed.hostname in {"fda.gov", "www.fda.gov"}:
        return urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment))
    return value


def sanitize_feed_xml(payload: bytes) -> bytes:
    """Replace HTML-only named entities that make otherwise useful XML invalid.

    RSS publishers occasionally emit entities such as ``&ndash;`` without a
    DTD. XML's five predefined entities are preserved, recognized HTML names
    become Unicode, and unknown names become harmless literal text.
    """
    predefined = {"amp", "lt", "gt", "quot", "apos"}

    def replace_entity(match: re.Match[bytes]) -> bytes:
        name = match.group(1).decode("ascii")
        if name in predefined:
            return match.group(0)
        replacement = html5.get(f"{name};")
        if replacement is not None:
            return replacement.encode("utf-8")
        return f"&amp;{name};".encode("ascii")

    return re.sub(rb"&([A-Za-z][A-Za-z0-9]+);", replace_entity, payload)


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
    request = urllib.request.Request(
        source.url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AgewellBrief/0.6; +https://agewellbrief.com/about)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(sanitize_feed_xml(response.read()))

    entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] in {"item", "entry"}]
    results: list[FeedItem] = []
    for item in entries:
        link = child_text(item, ("link",))
        if not link:
            for node in list(item):
                if node.tag.rsplit("}", 1)[-1] == "link" and node.attrib.get("href"):
                    link = node.attrib["href"]
                    break
        link = normalize_source_url(link)
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
        "consumer safety": ("health fraud", "tainted", "hidden drug", "product notification", "recall"),
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
    """Use an offer only when it is explicitly assigned to the article category."""
    return configured_offers.get(category)


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
    evidence: EvidencePacket | None = None,
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
        "evidence_packet": evidence.to_dict() if evidence else None,
        "requirements": [
            "Write clear, engaging health journalism for readers over 50.",
            "Use only claims supported by the supplied source material.",
            "Do not diagnose, prescribe, promise results, or invent institutions or studies.",
            "Do not imply that a supplement treats or cures a disease.",
            "Write with tension, specificity, agency, and warmth; avoid hype and filler.",
            "bullets must contain exactly three items, each at most 20 words.",
            *PUBLICATION_STYLE_REQUIREMENTS,
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
    photo: PublishedImage | None = None,
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
    image_frontmatter = ""
    if photo:
        image_frontmatter = f'''image_provider: "{quote(photo.provider)}"
image_provider_id: "{quote(photo.provider_id)}"
image: "{quote(photo.local_url)}"
image_alt: "{quote(photo.alt)}"
image_width: {photo.width}
image_height: {photo.height}
image_photographer: "{quote(photo.creator)}"
image_photographer_url: "{quote(photo.creator_url)}"
image_source_url: "{quote(photo.source_url)}"
image_review_status: "{quote(photo.review_status)}"
image_avg_color: "{photo.avg_color}"
'''
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
{image_frontmatter}---

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
    image_cache = ImageSearchCache(IMAGE_CACHE_FILE)
    used_image_ids = load_image_ledger(IMAGE_LEDGER_FILE)
    used_image_creators = load_image_creators(IMAGE_LEDGER_FILE)
    vision_reviewer = DeferredVisionReviewer()

    edition_time = dt.datetime.now(dt.timezone.utc)
    recorder = EditionRecorder(EDITION_STATE_ROOT, edition_time)
    candidates = fetch_ranked_items(sources, state, max(MAX_ITEMS, CANDIDATE_POOL_SIZE))
    source_artifacts: list[dict[str, Any]] = []
    evidence_artifacts: list[dict[str, Any]] = []
    draft_artifacts: list[dict[str, Any]] = []
    brief_artifacts: list[dict[str, Any]] = []
    candidate_artifacts: list[dict[str, Any]] = []
    review_artifacts: list[dict[str, Any]] = []
    release_checks: list[dict[str, Any]] = []

    for index, (item, content_type, source_text) in enumerate(choose_edition(candidates)):
        key = item_id(item)
        category = classify(item)
        source_material = source_text or item.summary
        source_artifacts.append(
            {
                "article_id": key,
                "title": item.title,
                "url": item.link,
                "source_name": item.source_name,
                "category": category,
                "content_type": content_type,
                "source_characters": len(source_material),
            }
        )

        try:
            evidence = build_evidence_packet(
                client,
                MODEL,
                item.title,
                item.summary,
                source_material,
                item.link,
            )
        except Exception as exc:
            print(f"Evidence agent fallback ({item.source_name}): {exc}", file=sys.stderr)
            evidence = EvidencePacket(
                study_type="reported health research",
                key_claims=(item.summary or item.title,),
                limitations=("The source did not expose enough detail for a fuller evidence extraction.",),
                what_not_to_say=("Do not claim causation, treatment, or guaranteed personal benefit.",),
                confidence="unclear",
            )
        evidence_artifacts.append({"article_id": key, **evidence.to_dict()})

        content = draft(client, item, category, content_type, source_text, evidence)
        draft_artifacts.append({"article_id": key, "content_type": content_type, **content})

        try:
            image_brief = direct_image(client, MODEL, item.title, category, content)
        except Exception as exc:
            print(f"Image director fallback ({item.source_name}): {exc}", file=sys.stderr)
            image_brief = ImageBrief(
                editorial_intent="Show the story's practical human context without making a medical promise.",
                subject="an authentic adult in a relevant everyday or research setting",
                setting="natural light and a credible real-world environment",
                mood="capable, alert, and unstaged",
                composition="landscape editorial photograph with one clear focal subject",
                avoid=("fearful expressions", "product advertising", "patronizing retirement stereotypes"),
                search_queries=(f"{category} adult daily life", "health research natural light", "active adult everyday life"),
            )
        brief_artifacts.append({"article_id": key, **image_brief.to_dict()})

        image_candidates = search_image_candidates(
            image_brief,
            PEXELS_API_KEY,
            PIXABAY_API_KEY,
            image_cache,
            used_image_ids,
            used_image_creators,
        )
        candidate_artifacts.append(
            {
                "article_id": key,
                "query": image_brief.search_queries[0],
                "candidates": [candidate.to_dict() for candidate in image_candidates],
            }
        )

        photo: PublishedImage | None = None
        alignment: AlignmentReview | None = None
        selected_candidate = None
        visual_review: dict[str, Any] = {
            "status": "pending",
            "reason": "No suitable image candidate was available.",
        }
        if image_candidates:
            try:
                alignment = review_image_metadata(
                    client,
                    MODEL,
                    content,
                    image_brief,
                    [candidate.to_dict() for candidate in image_candidates],
                )
            except Exception as exc:
                print(f"Image proofreader fallback ({item.source_name}): {exc}", file=sys.stderr)
                alignment = AlignmentReview(
                    selected_candidate_id=image_candidates[0].candidate_id,
                    score=50,
                    rationale="Deterministic fallback selected the strongest available landscape candidate.",
                    concerns=("Metadata proofreader was unavailable.",),
                    metadata_status="pending",
                )
            selected_candidate = next(
                (candidate for candidate in image_candidates if candidate.candidate_id == alignment.selected_candidate_id),
                None,
            )
            if selected_candidate and alignment.metadata_status != "rejected":
                try:
                    article_slug = f"{slug(content['headline'])}-{key[:8]}"
                    photo = persist_image(selected_candidate, PUBLIC_ROOT, recorder.edition_id, article_slug)
                    visual_review = vision_reviewer.review(str(PUBLIC_ROOT / photo.local_url.lstrip("/")), image_brief, content)
                    append_image_ledger(IMAGE_LEDGER_FILE, selected_candidate, key, recorder.edition_id)
                    used_image_ids.add(selected_candidate.candidate_id)
                    if selected_candidate.creator_url:
                        used_image_creators.add(selected_candidate.creator_url)
                except Exception as exc:
                    print(f"Selected image failed ({item.source_name}): {exc}", file=sys.stderr)
                    photo = None

        metadata_status = alignment.metadata_status if alignment else "missing"
        visual_status = str(visual_review.get("status", "pending"))
        review_artifacts.append(
            {
                "article_id": key,
                "metadata_review": alignment.to_dict() if alignment else None,
                "visual_review": visual_review,
            }
        )

        offer_url = None
        if content_type == "lead":
            offer_url = tracked_offer_url(select_offer(configured_offers, category), category, key)
        target = OUTPUT_DIR / f"{recorder.edition_id}-{slug(content['headline'])}-{key[:8]}.md"
        target.write_text(
            markdown(item, category, content, offer_url, content_type, index + 1, edition_time, photo),
            encoding="utf-8",
        )
        release_checks.append(
            audit_release(key, item.link, content, metadata_status, visual_status).to_dict()
        )
        state.add(key)
        save_state(state)
        print(f"Wrote {target}")

    recorder.write("sources", source_artifacts)
    recorder.write("evidence", evidence_artifacts)
    recorder.write("drafts", draft_artifacts)
    recorder.write("image-briefs", brief_artifacts)
    recorder.write("candidates", candidate_artifacts)
    recorder.write("visual-reviews", review_artifacts)
    recorder.write(
        "release-manifest",
        {
            "edition_id": recorder.edition_id,
            "run_id": recorder.run_id,
            "generated_at": edition_time.isoformat(),
            "publishable": bool(release_checks) and all(check["publishable"] for check in release_checks),
            "checks": release_checks,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
