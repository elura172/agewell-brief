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
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup
from openai import OpenAI

from agewell.affiliates import load_health_status, select_offer, select_offers, tracked_offer_url
from agewell.agents import assignment_editor, commercial_integrity, copy_edit, release_manager
from agewell.context import ContextHit, build_context_index, retrieve_context
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
TREND_CANDIDATE_MIN_SCORE = float(os.getenv("TREND_CANDIDATE_MIN_SCORE", "14"))
AUTO_PUBLISH = os.getenv("AUTO_PUBLISH", "false").lower() in {"1", "true", "yes"}
AUTO_PUBLISH_UNTIL = os.getenv("AUTO_PUBLISH_UNTIL", "")
PUBLIC_ROOT = Path(os.getenv("PUBLIC_ROOT", ROOT / "public"))
EDITION_STATE_ROOT = Path(os.getenv("EDITION_STATE_ROOT", ROOT / ".state/editions"))
IMAGE_CACHE_FILE = Path(os.getenv("IMAGE_CACHE_FILE", ROOT / ".state/image-search-cache.json"))
IMAGE_LEDGER_FILE = Path(os.getenv("IMAGE_LEDGER_FILE", ROOT / ".state/image-ledger.json"))
AFFILIATE_HEALTH_FILE = Path(os.getenv("AFFILIATE_HEALTH_FILE", ROOT / ".state/affiliate-health.json"))
AFFILIATE_REVIEW_FILE = Path(os.getenv("AFFILIATE_REVIEW_FILE", ROOT / "config/affiliate-offer-review.json"))
TREND_RADAR_FILE = Path(os.getenv("TREND_RADAR_FILE", ROOT / ".state/trend-radar.json"))
PROGRAM_RESOURCES_JSON = os.getenv("PROGRAM_RESOURCES_JSON", "{}")

PUBLICATION_STYLE_REQUIREMENTS = (
    "Use Agewell's publication register: clear, spirited, respectful, and concrete.",
    "Vary sentence length naturally and prefer direct verbs over inflated significance language.",
    "Remove promotional phrasing, vague attribution, filler, manufactured punchlines, and generic future-looking conclusions.",
    "Use sentence case for section headings.",
    "Do not invent facts, quotations, colour, or scenes to make the writing feel more human.",
    "Treat these as editing preferences, not a rigid template; clarity and factual nuance outrank style rules.",
)


class LeadTooShortError(ValueError):
    def __init__(self, word_count: int, minimum_words: int):
        self.word_count = word_count
        self.minimum_words = minimum_words
        super().__init__(f"lead draft is too short ({word_count} words; minimum {minimum_words})")


class DraftGenerationError(RuntimeError):
    """Raised after model output fails validation, with responses retained for review."""

    def __init__(self, attempts: list[dict[str, Any]]):
        self.attempts = attempts
        last_error = attempts[-1]["error"] if attempts else "unknown validation error"
        super().__init__(f"DeepSeek returned an invalid draft twice: {last_error}")


def auto_publish_enabled(now: dt.datetime | None = None) -> bool:
    """Enable hands-off publication only while the configured trial window is active."""
    if not AUTO_PUBLISH:
        return False
    if not AUTO_PUBLISH_UNTIL:
        return True
    try:
        cutoff = dt.date.fromisoformat(AUTO_PUBLISH_UNTIL)
    except ValueError:
        return False
    current = (now or dt.datetime.now(dt.timezone.utc)).date()
    return current < cutoff


@dataclass(frozen=True)
class FeedSource:
    name: str
    url: str
    priority: int = 0
    headline_mode: str = "rewrite"
    publisher: str = ""
    authority: str = "editorial"
    categories: tuple[str, ...] = ()
    max_daily_items: int = 2
    requires_secondary_check: bool = False


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


def parse_model_json(raw_content: str) -> dict[str, Any]:
    """Parse one model JSON object while tolerating harmless duplicated closers."""
    stripped = raw_content.strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as exc:
        value, parsed_end = json.JSONDecoder().raw_decode(stripped)
        trailing = stripped[parsed_end:].strip()
        if trailing and not re.fullmatch(r"[}\]`]+", trailing):
            raise exc
    if not isinstance(value, dict):
        raise TypeError("draft response was not a JSON object")
    return value


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
                    authority=str(value.get("authority", "editorial")),
                    categories=tuple(str(category).lower() for category in value.get("categories", [])),
                    max_daily_items=max(1, int(value.get("max_daily_items", 2))),
                    requires_secondary_check=bool(value.get("requires_secondary_check", False)),
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


def load_trend_topics(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or TREND_RADAR_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    topics = payload.get("topics", []) if isinstance(payload, dict) else []
    return [topic for topic in topics if isinstance(topic, dict)]


def trend_score(item: FeedItem, topics: list[dict[str, Any]]) -> int:
    """Reward overlap with independently observed, fresh trend topics."""
    item_words = set(normalized_title(f"{item.title} {item.summary}").split())
    category = classify(item)
    best = 0
    for topic in topics:
        topic_words = set(normalized_title(f"{topic.get('topic', '')} {topic.get('headline', '')}").split())
        overlap = len(item_words & topic_words)
        if overlap < 2 and str(topic.get("category", "")).lower() != category:
            continue
        score = min(6, overlap * 2) + min(4, int(topic.get("source_count", 0) or 0))
        if str(topic.get("category", "")).lower() == category:
            score += 3
        if float(topic.get("score", 0) or 0) >= 12:
            score += 2
        best = max(best, score)
    return best


def trend_candidates(topics: list[dict[str, Any]]) -> list[FeedItem]:
    """Convert strong radar signals into draft candidates for source review."""
    results: list[FeedItem] = []
    seen: set[str] = set()
    for topic in topics:
        if float(topic.get("score", 0) or 0) < TREND_CANDIDATE_MIN_SCORE:
            continue
        category = str(topic.get("category") or "general wellness").lower()
        for raw in topic.get("items", [])[:3]:
            if not isinstance(raw, dict):
                continue
            link = str(raw.get("link") or "").strip()
            title = str(raw.get("title") or "").strip()
            if not link or not title or link in seen:
                continue
            seen.add(link)
            source = str(raw.get("source") or "Trend discovery").strip()
            results.append(
                FeedItem(
                    title=title,
                    summary=title,
                    link=link,
                    published=str(raw.get("published") or ""),
                    source_name=source,
                    source_priority=4,
                    headline_mode="preserve",
                    source_group=source,
                )
            )
    return results


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

    topics = load_trend_topics()
    candidates.extend(trend_candidates(topics))
    if processed:
        candidates = [item for item in candidates if item_id(item) not in processed]
    return select_ranked_items(candidates, limit, topics)


def select_ranked_items(
    candidates: list[FeedItem],
    limit: int | None = None,
    trend_topics: list[dict[str, Any]] | None = None,
) -> list[FeedItem]:
    """Deduplicate and rank stories while keeping each batch source-diverse."""
    target_count = limit if limit is not None else MAX_ITEMS
    best_by_title: dict[str, FeedItem] = {}
    for item in candidates:
        key = normalized_title(item.title)
        current = best_by_title.get(key)
        if current is None or relevance_score(item) > relevance_score(current):
            best_by_title[key] = item

    topics = trend_topics or []
    ranked = sorted(
        best_by_title.values(),
        key=lambda item: relevance_score(item) + trend_score(item, topics),
        reverse=True,
    )
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
    signal_entries = [(signal, "signal", fetch_article_text(signal)) for signal in signals]
    return [(lead, "lead", lead_source)] + signal_entries


def classify(item: FeedItem) -> str:
    text = f"{item.title} {item.summary}".lower()
    rules = {
        "consumer safety": ("health fraud", "tainted", "hidden drug", "product notification", "recall"),
        "men's health": (
            "men's health",
            "male sexual health",
            "erectile",
            "prostate",
            "testosterone",
            "male fertility",
            "libido",
        ),
        "metabolic health": ("blood sugar", "glucose", "insulin", "metabolic", "diabetes", "obesity", "lipid"),
        "detoxification": ("detox", "detoxification", "chelation", "heavy metal", "phase 1", "phase 2", "transport clearing", "elimination pathway"),
        "gut health": ("gut health", "microbiome", "candida", "probiotic", "prebiotic", "bloating", "digestive"),
        "cellular senescence": ("senescent", "senolytic", "zombie cell", "cell shedding", "fisetin", "quercetin", "cellular senescence"),
        "mobility": ("joint", "arthritis", "knee", "back pain", "balance training", "fall prevention", "walking"),
        "brain health": ("memory", "cognition", "brain", "dementia", "alzheimer", "parkinson"),
        "sleep health": ("sleep", "insomnia", "circadian", "bedtime", "rem sleep", "night waking"),
        "longevity": ("aging", "ageing", "longevity", "lifespan", "healthspan"),
    }
    for category, terms in rules.items():
        if any(term in text for term in terms):
            return category
    return "general wellness"


def offers() -> dict[str, Any]:
    raw = os.getenv("AFFILIATE_OFFERS_JSON", "{}")
    try:
        value = json.loads(raw)
        configured = value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        print("Ignoring invalid AFFILIATE_OFFERS_JSON", file=sys.stderr)
        configured = {}

    # A reviewed file can replace the neutral general-wellness bucket with a
    # contextual category after a landing-page classification pass.  URLs are
    # de-duplicated by the reviewed entry, so the secret remains the fallback.
    try:
        reviewed = json.loads(AFFILIATE_REVIEW_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        reviewed = {}
    reviewed_offers = reviewed.get("offers", []) if isinstance(reviewed, dict) else []
    if not isinstance(reviewed_offers, list) or not reviewed_offers:
        return configured
    base_offers = configured.get("offers", []) if isinstance(configured.get("offers"), list) else []
    reviewed_urls = {str(item.get("url", "")) for item in reviewed_offers if isinstance(item, dict)}
    merged = [item for item in base_offers if not (isinstance(item, dict) and item.get("url") in reviewed_urls)]
    configured = dict(configured)
    configured["offers"] = merged + reviewed_offers
    return configured
def draft(
    client: OpenAI,
    item: FeedItem,
    category: str,
    content_type: str = "signal",
    source_text: str | None = None,
    evidence: EvidencePacket | None = None,
    evergreen_context: list[ContextHit] | None = None,
) -> dict[str, Any]:
    is_longform = content_type in {"lead", "evergreen", "editorial"}
    source_material = source_text or item.summary
    source_is_deep = len(source_material) >= MIN_LEAD_SOURCE_CHARS
    minimum_lead_words = 500 if source_is_deep else 300
    focused_fallback_words = 350 if source_is_deep else 250
    prompt: dict[str, Any] = {
        "source_title": item.title,
        "source_summary": item.summary[:5000],
        "source_material": source_material[:LEAD_SOURCE_CHARS],
        "source_url": item.link,
        "source_name": item.source_name,
        "category": category,
        "content_type": content_type,
        "evidence_packet": evidence.to_dict() if evidence else None,
        "evergreen_context": [hit.prompt_dict() for hit in (evergreen_context or [])],
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
    if is_longform:
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
            (
                "Use evergreen_context only for background framing, questions, or vocabulary. "
                "Never present it as current evidence, a clinical recommendation, or proof of a health effect."
            ),
            "Do not mention a program, course, or private file path in the published article unless explicitly requested.",
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
            "content": (
                "You are Agewell Brief's health-news editor. Write for capable adults in later life. "
                "Be clear, spirited, warm, and precise. Use hopeful, useful framing without manufacturing reassurance. "
                "Make the copy easy to scan with short paragraphs, strong transitions, and occasional concise bullets, "
                "but vary sentence length naturally and preserve an intelligent human voice. "
                "Build curiosity from the actual finding, not fear, false urgency, or exaggerated promises. "
                "Separate what the source reports from what it may suggest and what remains unknown. "
                "Never invent studies, quotes, institutions, outcomes, diagnoses, treatments, or product benefits. "
                "Do not turn association into causation or give individualized medical advice. "
                "Affiliate relationships must never influence story selection, headline framing, interpretation, or evidence. "
                "CSS controls typography and accessibility; do not add typographic markup as a substitute for good writing."
            ),
        },
        {"role": "user", "content": json.dumps(prompt)},
    ]
    result: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] = []
    for attempt_number in range(1, 3):
        raw_content = ""
        candidate: dict[str, Any] | None = None
        try:
            response = client.chat.completions.create(
                model=MODEL,
                temperature=0.2,
                max_tokens=3200 if is_longform else 1400,
                response_format={"type": "json_object"},
                messages=messages,
                extra_body={"thinking": {"type": "disabled"}},
            )
            raw_content = response.choices[0].message.content or "{}"
            candidate = parse_model_json(raw_content)
            if is_longform:
                raw_sections = candidate.get("sections")
                if not isinstance(raw_sections, list) or len(raw_sections) != 4:
                    raise ValueError("lead draft requires four sections")
                for section in raw_sections:
                    if not isinstance(section, dict) or not clean_text(str(section.get("heading", ""))):
                        raise ValueError("lead section requires a heading")
                    paragraphs = section.get("paragraphs")
                    if not isinstance(paragraphs, list) or not 2 <= len(paragraphs) <= 3:
                        raise ValueError("each lead section requires two or three paragraphs")
                    if any(not clean_text(str(paragraph)) for paragraph in paragraphs):
                        raise ValueError("lead section contains an empty paragraph")
                lead_words = len(
                    " ".join(
                        str(paragraph)
                        for section in raw_sections
                        if isinstance(section, dict)
                        for paragraph in section.get("paragraphs", [])
                    ).split()
                )
                if lead_words < minimum_lead_words:
                    raise LeadTooShortError(lead_words, minimum_lead_words)
            result = candidate
            break
        except Exception as exc:
            attempts.append(
                {
                    "attempt": attempt_number,
                    "error": str(exc),
                    "raw_response": raw_content,
                }
            )
            if (
                attempt_number == 2
                and is_longform
                and isinstance(exc, LeadTooShortError)
                and exc.word_count >= focused_fallback_words
                and candidate is not None
            ):
                candidate["generation_status"] = "accepted_focused_fallback"
                candidate["generation_note"] = (
                    f"The repaired lead contains {exc.word_count} words; retained as a focused draft "
                    f"for human review instead of the {minimum_lead_words}-word target."
                )
                result = candidate
                break
            if attempt_number == 1 and raw_content:
                repair_request = {
                    "task": "Repair and return the complete draft as one valid JSON object.",
                    "validation_error": str(exc),
                    "requirements": [
                        "Preserve only source-supported claims from the original request.",
                        "Return every required field and the complete article, not a patch or commentary.",
                    ],
                }
                if is_longform:
                    repair_request["requirements"].append(
                        f"Expand the four sections to at least {minimum_lead_words} words total without repetition or unsupported detail."
                    )
                messages.extend(
                    [
                        {"role": "assistant", "content": raw_content},
                        {"role": "user", "content": json.dumps(repair_request)},
                    ]
                )
    if result is None:
        raise DraftGenerationError(attempts)
    generated_headline = clean_text(result.get("headline")) or item.title
    headline = item.title if item.headline_mode == "preserve" else generated_headline
    dek = clean_text(result.get("dek")) or item.summary
    bullets = result.get("bullets")
    if not isinstance(bullets, list) or len(bullets) != 3:
        bullets = ["The source reports a new health-related finding.", "The result needs context before changing routines.", "Discuss personal decisions with a qualified clinician."]
    caveat = clean_text(result.get("caveat")) or "This brief is informational and is not medical advice."
    sections: list[dict[str, Any]] = []
    if is_longform:
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
    normalized = {
        "headline": headline,
        "dek": dek,
        "bullets": [clean_text(str(x)) for x in bullets],
        "caveat": caveat,
        "sections": sections,
    }
    if result.get("generation_status"):
        normalized["generation_status"] = clean_text(str(result["generation_status"]))
    if result.get("generation_note"):
        normalized["generation_note"] = clean_text(str(result["generation_note"]))
    return normalized


def quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def resource_heading(category: str) -> str:
    """Give a resource card a useful editorial heading without making claims."""
    headings = {
        "sleep health": "A practical follow-up for steadier routines",
        "brain health": "A practical follow-up for staying mentally engaged",
        "cellular senescence": "A practical follow-up for the cellular-aging conversation",
        "detoxification": "A structured resource for the body's clearing pathways",
        "gut health": "A practical follow-up for a steadier gut routine",
        "mobility": "A practical follow-up for everyday movement",
        "longevity": "A practical follow-up for healthy aging",
        "metabolic health": "A practical follow-up for everyday habits",
    }
    return headings.get(category.lower(), "A practical follow-up to explore")


def resource_card(url: str, category: str, *, primary: bool = False, first_party: bool = False) -> str:
    label = "Practical follow-up" if primary else "More to explore"
    heading = resource_heading(category)
    intro = (
        f"For readers interested in taking the ideas in this {category} brief a step further, "
        "we’ve included an optional resource that may be useful."
        if primary
        else "An optional resource for readers who want another place to begin."
    )
    disclosure = (
        "This is part of our program. We may earn a commission if you purchase through this link; there is no added cost to you."
        if first_party
        else "Commission-supported; no added cost to you."
    )
    rel = "noopener noreferrer"
    return f'''\n\n<aside class="resource-card{' resource-card--primary' if primary else ''}" aria-label="{label}">
<p class="resource-kicker">{label}</p>
<h3>{heading}</h3>
<p>{intro}</p>
<p><a class="resource-link" href="{url}" rel="{rel}">Explore the resource <span aria-hidden="true">→</span></a></p>
<p class="resource-disclosure">{disclosure}</p>
</aside>'''


def program_resources() -> dict[str, str]:
    try:
        value = json.loads(PROGRAM_RESOURCES_JSON)
    except json.JSONDecodeError:
        return {}
    if not isinstance(value, dict):
        return {}
    return {
        str(category).lower(): str(url)
        for category, url in value.items()
        if isinstance(url, str) and url.startswith("https://")
    }


def program_resource_for(category: str, item: FeedItem, resources: dict[str, str]) -> str | None:
    """Choose a first-party resource by editorial category and article wording."""
    normalized_category = category.strip().lower()
    text = f"{item.title} {item.summary}".lower()
    if normalized_category == "detoxification":
        if any(term in text for term in ("mineral", "chelation", "heavy metal", "zeolite", "kaolin", "charcoal")):
            return resources.get("dark mirror") or resources.get("detoxification")
        return resources.get("living waters") or resources.get("detoxification")
    aliases = {
        "cellular senescence": "cell shedding",
        "gut health": "inner garden",
        "metabolic health": "higher flame",
        "brain health": "luminous mind",
    }
    return resources.get(aliases.get(normalized_category, normalized_category))


def markdown(
    item: FeedItem,
    category: str,
    content: dict[str, Any],
    offer_urls: list[str] | str | None,
    content_type: str = "signal",
    edition_rank: int = 1,
    edition_time: dt.datetime | None = None,
    photo: PublishedImage | None = None,
    draft: bool = True,
    program_url: str | None = None,
) -> str:
    published_at = edition_time or dt.datetime.now(dt.timezone.utc)
    bullets = "\n".join(f"- {bullet}" for bullet in content["bullets"])
    if isinstance(offer_urls, str):
        offer_urls = [offer_urls] if offer_urls else []
    offer_urls = list(offer_urls or [])[:3]
    recommendation_top = ""
    recommendation = ""
    program_card = resource_card(program_url, category, primary=True, first_party=True) if program_url else ""
    if offer_urls:
        placement_count = min(3, max(2, len(offer_urls)))
        placements = [offer_urls[index % len(offer_urls)] for index in range(placement_count)]
        recommendation_top = resource_card(placements[0], category, primary=True)
        if len(offer_urls) > 1:
            recommendation = resource_card(placements[1], category)
        else:
            recommendation = resource_card(placements[0], category)
        if len(offer_urls) > 2:
            recommendation += resource_card(placements[2], category)
    sections = ""
    if content_type in {"lead", "evergreen", "editorial"}:
        section_blocks = [
            f"## {section['heading']}\n\n" + "\n\n".join(section["paragraphs"])
            for section in content.get("sections", [])
        ]
        if section_blocks and (program_card or recommendation_top):
            section_blocks.insert(1, program_card or recommendation_top)
        sections = "\n\n".join(section_blocks)
    health_note = content["caveat"]
    image_frontmatter = ""
    if photo:
        image_frontmatter = f'''image_provider: "{quote(photo.provider)}"
image_provider_id: "{quote(photo.provider_id)}"
image: "{quote(photo.local_url)}"
image_alt: "{quote(photo.alt)}"
image_caption: "A glimpse of the everyday routines behind this story."
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
draft: {str(draft).lower()}
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
{(program_card or recommendation_top) if not sections else (recommendation_top if content_type not in {"lead", "evergreen", "editorial"} else "")}

### Source

This {"analysis" if content_type == "lead" else content_type} is based on [{item.title}]({item.link}) from {item.source_name}. Read the original report for full context.
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
    configured_program_resources = program_resources()
    affiliate_health = load_health_status(AFFILIATE_HEALTH_FILE)
    image_cache = ImageSearchCache(IMAGE_CACHE_FILE)
    used_image_ids = load_image_ledger(IMAGE_LEDGER_FILE)
    used_image_creators = load_image_creators(IMAGE_LEDGER_FILE)
    vision_reviewer = DeferredVisionReviewer()
    evergreen_documents = build_context_index()

    edition_time = dt.datetime.now(dt.timezone.utc)
    publish_automatically = auto_publish_enabled(edition_time)
    recorder = EditionRecorder(EDITION_STATE_ROOT, edition_time)
    candidates = fetch_ranked_items(sources, state, max(MAX_ITEMS, CANDIDATE_POOL_SIZE))
    trend_topics = load_trend_topics()
    recent_titles = [path.stem for path in sorted(OUTPUT_DIR.glob("*.md"))[-40:]]
    assignment = assignment_editor(client, MODEL, candidates, trend_topics, recent_titles, MAX_ITEMS)
    candidate_by_id = {item_id(item): item for item in candidates}
    assigned_candidates = [
        candidate_by_id[row["article_id"]]
        for row in assignment["assignments"]
        if row.get("article_id") in candidate_by_id
    ]
    if not assigned_candidates:
        assigned_candidates = candidates
    source_artifacts: list[dict[str, Any]] = []
    evidence_artifacts: list[dict[str, Any]] = []
    draft_artifacts: list[dict[str, Any]] = []
    brief_artifacts: list[dict[str, Any]] = []
    candidate_artifacts: list[dict[str, Any]] = []
    review_artifacts: list[dict[str, Any]] = []
    context_artifacts: list[dict[str, Any]] = []
    copy_artifacts: list[dict[str, Any]] = []
    commercial_artifacts: list[dict[str, Any]] = []
    release_checks: list[dict[str, Any]] = []
    failure_artifacts: list[dict[str, Any]] = []
    generated_count = 0
    edition_entries = choose_edition(assigned_candidates)

    for item, requested_content_type, source_text in edition_entries:
        key = item_id(item)
        category = classify(item)
        source_material = source_text or item.summary
        content_type = requested_content_type
        evergreen_context = retrieve_context(
            f"{item.title} {item.summary} {category}",
            evergreen_documents,
        )
        context_artifacts.append(
            {
                "article_id": key,
                "enabled": bool(evergreen_documents),
                "hits": [hit.audit_dict() for hit in evergreen_context],
                "policy": "Background framing only; never current medical evidence.",
            }
        )
        source_artifacts.append(
            {
                "article_id": key,
                "title": item.title,
                "url": item.link,
                "source_name": item.source_name,
                "category": category,
                "content_type": requested_content_type,
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

        try:
            content = draft(client, item, category, content_type, source_text, evidence, evergreen_context)
        except Exception as exc:
            failure = {
                "article_id": key,
                "title": item.title,
                "source_url": item.link,
                "source_name": item.source_name,
                "stage": "draft",
                "requested_content_type": requested_content_type,
                "error": str(exc),
                "attempts": exc.attempts if isinstance(exc, DraftGenerationError) else [],
            }
            if requested_content_type == "lead":
                try:
                    content = draft(client, item, category, "signal", None, evidence, evergreen_context)
                    content_type = "signal"
                    failure["resolution"] = "downgraded_to_signal"
                    failure_artifacts.append(failure)
                    print(f"Lead downgraded to signal ({item.source_name}): {exc}", file=sys.stderr)
                except Exception as fallback_exc:
                    failure["resolution"] = "skipped"
                    failure["fallback_error"] = str(fallback_exc)
                    failure["fallback_attempts"] = (
                        fallback_exc.attempts if isinstance(fallback_exc, DraftGenerationError) else []
                    )
                    failure_artifacts.append(failure)
                    print(f"Draft skipped ({item.source_name}): {fallback_exc}", file=sys.stderr)
                    continue
            else:
                failure["resolution"] = "skipped"
                failure_artifacts.append(failure)
                print(f"Draft skipped ({item.source_name}): {exc}", file=sys.stderr)
                continue
        content, copy_review = copy_edit(client, MODEL, content, item.title)
        copy_artifacts.append({"article_id": key, **copy_review})
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

        offer_urls = [
            tracked_offer_url(url, category, key)
            for url in select_offers(configured_offers, category, key, affiliate_health, limit=3)
        ]
        offer_review = commercial_integrity(category, offer_urls)
        commercial_artifacts.append({"article_id": key, **offer_review})
        release_review = release_manager(item.link, content, offer_review)
        release_check = audit_release(
            key,
            item.link,
            content,
            metadata_status,
            visual_status,
            require_human_review=not publish_automatically,
            require_visual_review=not publish_automatically,
        )
        generated_count += 1
        target = OUTPUT_DIR / f"{recorder.edition_id}-{slug(content['headline'])}-{key[:8]}.md"
        target.write_text(
            markdown(
                item,
                category,
                content,
                offer_urls,
                content_type,
                generated_count,
                edition_time,
                photo,
                draft=not (publish_automatically and release_check.publishable),
                program_url=program_resource_for(category, item, configured_program_resources),
            ),
            encoding="utf-8",
        )
        release_checks.append(
            {**release_check.to_dict(), "desk_review": release_review}
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
    recorder.write("evergreen-context", context_artifacts)
    recorder.write("failed-drafts", failure_artifacts)
    recorder.write("assignments", assignment)
    recorder.write("copy-reviews", copy_artifacts)
    recorder.write("commercial-reviews", commercial_artifacts)
    recorder.write(
        "release-manifest",
        {
            "edition_id": recorder.edition_id,
            "run_id": recorder.run_id,
            "generated_at": edition_time.isoformat(),
            "attempted_stories": len(edition_entries),
            "generated_stories": generated_count,
            "failed_stories": sum(1 for failure in failure_artifacts if failure.get("resolution") == "skipped"),
            "publishable": bool(release_checks) and all(check["publishable"] for check in release_checks),
            "checks": release_checks,
        },
    )
    return 0 if generated_count or not edition_entries else 1


if __name__ == "__main__":
    raise SystemExit(run())
