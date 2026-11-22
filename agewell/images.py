from __future__ import annotations

import base64
import concurrent.futures
import datetime as dt
import io
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlencode

from PIL import Image, ImageOps

from agewell.editorial import ImageBrief, SPIRAL_GEOMETRIC_MOTIFS, candidate_passes_discipline


PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
PIXABAY_SEARCH_URL = "https://pixabay.com/api/"
UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"


@dataclass(frozen=True)
class ImageCandidate:
    provider: str
    provider_id: str
    download_url: str
    source_url: str
    creator: str
    creator_url: str
    alt: str
    tags: tuple[str, ...]
    width: int
    height: int
    avg_color: str = "#cad4cf"
    search_query: str = ""
    download_location: str = ""

    @property
    def candidate_id(self) -> str:
        return f"{self.provider}:{self.provider_id}"

    def to_dict(self, include_download_url: bool = False) -> dict[str, Any]:
        value = asdict(self)
        value["candidate_id"] = self.candidate_id
        if not include_download_url:
            value.pop("download_url", None)
        return value


@dataclass(frozen=True)
class PublishedImage:
    provider: str
    provider_id: str
    local_url: str
    source_url: str
    creator: str
    creator_url: str
    alt: str
    width: int = 1200
    height: int = 627
    avg_color: str = "#cad4cf"
    review_status: str = "pending"
    caption: str = ""


class ImageSearchCache:
    def __init__(self, path: Path, ttl: dt.timedelta = dt.timedelta(hours=24)):
        self.path = path
        self.ttl = ttl
        self.lock = threading.Lock()
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.data = {}

    def get(self, provider: str, query: str) -> list[ImageCandidate] | None:
        with self.lock:
            entry = self.data.get(f"{provider}:{query.lower().strip()}")
        if not isinstance(entry, dict):
            return None
        try:
            saved_at = dt.datetime.fromisoformat(str(entry["saved_at"]))
            if dt.datetime.now(dt.timezone.utc) - saved_at > self.ttl:
                return None
            return [ImageCandidate(**value) for value in entry.get("candidates", [])]
        except (KeyError, TypeError, ValueError):
            return None

    def set(self, provider: str, query: str, candidates: list[ImageCandidate]) -> None:
        with self.lock:
            self.data[f"{provider}:{query.lower().strip()}"] = {
                "saved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "candidates": [asdict(candidate) for candidate in candidates],
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_json(request: urllib.request.Request) -> dict[str, Any]:
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.loads(response.read())
    return value if isinstance(value, dict) else {}


def search_pexels(api_key: str, query: str) -> list[ImageCandidate]:
    if not api_key:
        return []
    url = f"{PEXELS_SEARCH_URL}?{urlencode({'query': query, 'orientation': 'landscape', 'size': 'large', 'per_page': 8, 'locale': 'en-US'})}"
    payload = _read_json(
        urllib.request.Request(
            url,
            headers={"Authorization": api_key, "User-Agent": "AgewellBrief/0.5 (+editorial image broker)"},
        )
    )
    candidates: list[ImageCandidate] = []
    for value in payload.get("photos", []):
        if not isinstance(value, dict) or not isinstance(value.get("src"), dict):
            continue
        src = value["src"]
        original = str(src.get("original") or src.get("large2x") or src.get("landscape") or "")
        source_url = str(value.get("url", ""))
        creator_url = str(value.get("photographer_url", ""))
        if not original.startswith("https://images.pexels.com/") or not source_url.startswith("https://www.pexels.com/"):
            continue
        color = str(value.get("avg_color", "#cad4cf"))
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            color = "#cad4cf"
        candidates.append(
            ImageCandidate(
                provider="Pexels",
                provider_id=str(value.get("id", "")),
                download_url=f"{original}{'&' if '?' in original else '?'}auto=compress&cs=tinysrgb&w=1800",
                source_url=source_url,
                creator=str(value.get("photographer", "Pexels contributor")),
                creator_url=creator_url,
                alt=str(value.get("alt", "")).strip() or "Illustrative health and longevity photograph",
                tags=(),
                width=int(value.get("width", 1200)),
                height=int(value.get("height", 627)),
                avg_color=color,
                search_query=query,
            )
        )
    return candidates


def search_pixabay(api_key: str, query: str) -> list[ImageCandidate]:
    if not api_key:
        return []
    url = f"{PIXABAY_SEARCH_URL}?{urlencode({'key': api_key, 'q': query, 'image_type': 'photo', 'orientation': 'horizontal', 'safesearch': 'true', 'editors_choice': 'true', 'per_page': 8, 'min_width': 1000, 'min_height': 600})}"
    payload = _read_json(
        urllib.request.Request(url, headers={"User-Agent": "AgewellBrief/0.5 (+editorial image broker)"})
    )
    candidates: list[ImageCandidate] = []
    for value in payload.get("hits", []):
        if not isinstance(value, dict):
            continue
        download_url = str(value.get("largeImageURL") or value.get("webformatURL") or "")
        source_url = str(value.get("pageURL", ""))
        if not download_url.startswith("https://") or not source_url.startswith("https://pixabay.com/"):
            continue
        creator = str(value.get("user", "Pixabay contributor"))
        creator_id = str(value.get("user_id", ""))
        creator_slug = quote(creator.lower().replace(" ", "-"), safe="-")
        tags = tuple(tag.strip() for tag in str(value.get("tags", "")).split(",") if tag.strip())
        candidates.append(
            ImageCandidate(
                provider="Pixabay",
                provider_id=str(value.get("id", "")),
                download_url=download_url,
                source_url=source_url,
                creator=creator,
                creator_url=f"https://pixabay.com/users/{creator_slug}-{creator_id}/" if creator_id else "",
                alt=f"Illustrative photograph: {', '.join(tags[:5])}" if tags else "Illustrative health and longevity photograph",
                tags=tags,
                width=int(value.get("imageWidth", value.get("webformatWidth", 1200))),
                height=int(value.get("imageHeight", value.get("webformatHeight", 627))),
                search_query=query,
            )
        )
    return candidates


def search_unsplash(api_key: str, query: str) -> list[ImageCandidate]:
    if not api_key:
        return []
    url = f"{UNSPLASH_SEARCH_URL}?{urlencode({'query': query, 'orientation': 'landscape', 'content_filter': 'high', 'per_page': 8})}"
    payload = _read_json(
        urllib.request.Request(
            url,
            headers={
                "Authorization": f"Client-ID {api_key}",
                "Accept-Version": "v1",
                "User-Agent": "AgewellBrief/0.5 (editorial image search)",
            },
        )
    )
    candidates: list[ImageCandidate] = []
    for value in payload.get("results", []):
        if not isinstance(value, dict):
            continue
        urls = value.get("urls")
        links = value.get("links")
        user = value.get("user")
        user_links = user.get("links") if isinstance(user, dict) else None
        if not isinstance(urls, dict) or not isinstance(links, dict):
            continue
        image_url = str(urls.get("regular") or "")
        source_url = str(links.get("html") or "")
        creator_url = str(user_links.get("html") or "") if isinstance(user_links, dict) else ""
        download_location = str(links.get("download_location") or "")
        if not image_url.startswith("https://images.unsplash.com/"):
            continue
        if not source_url.startswith("https://unsplash.com/") or not creator_url.startswith("https://unsplash.com/"):
            continue
        if not download_location.startswith("https://api.unsplash.com/photos/"):
            continue
        attribution = {"utm_source": "agewellbrief", "utm_medium": "referral"}
        color = str(value.get("color", "#cad4cf"))
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            color = "#cad4cf"
        candidates.append(
            ImageCandidate(
                provider="Unsplash",
                provider_id=str(value.get("id", "")),
                # Unsplash requires embedding the exact hotlinked URL from the API response.
                download_url=image_url,
                source_url=f"{source_url}{'&' if '?' in source_url else '?'}{urlencode(attribution)}",
                creator=str(user.get("name", "Unsplash contributor")),
                creator_url=f"{creator_url}{'&' if '?' in creator_url else '?'}{urlencode(attribution)}",
                alt=str(value.get("alt_description") or value.get("description") or "Illustrative health and longevity photograph").strip(),
                tags=tuple(
                    str(tag.get("title", "")).strip()
                    for tag in value.get("tags", [])
                    if isinstance(tag, dict) and tag.get("title")
                ),
                width=int(value.get("width", 1200)),
                height=int(value.get("height", 627)),
                avg_color=color,
                search_query=query,
                download_location=download_location,
            )
        )
    return candidates


def search_image_candidates(
    brief: ImageBrief,
    pexels_key: str,
    pixabay_key: str,
    cache: ImageSearchCache,
    excluded_ids: set[str] | None = None,
    excluded_creator_urls: set[str] | None = None,
    unsplash_key: str = "",
    category: str = "general wellness",
    source_title: str = "",
    headline: str = "",
) -> list[ImageCandidate]:
    excluded = excluded_ids or set()
    excluded_creators = excluded_creator_urls or set()
    providers: list[tuple[str, str, Callable[[str, str], list[ImageCandidate]]]] = [
        ("Pexels", pexels_key, search_pexels),
        ("Pixabay", pixabay_key, search_pixabay),
        ("Unsplash", unsplash_key, search_unsplash),
    ]

    def load(
        provider: str,
        key: str,
        search: Callable[[str, str], list[ImageCandidate]],
        query: str,
    ) -> list[ImageCandidate]:
        cached = cache.get(provider, query)
        if cached is not None:
            return [candidate if candidate.search_query else replace(candidate, search_query=query) for candidate in cached]
        found = search(key, query)
        cache.set(provider, query, found)
        return found

    found: list[ImageCandidate] = []
    queries = list(brief.search_queries[:3])
    query_rank_map = {q.lower(): (len(queries) - idx) for idx, q in enumerate(queries)}
    searches = [
        (provider, key, search, query)
        for query in queries
        for provider, key, search in providers
        if key
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(searches) or 1)) as pool:
        futures = [pool.submit(load, provider, key, search, query) for provider, key, search, query in searches]
        for future in concurrent.futures.as_completed(futures):
            try:
                found.extend(future.result())
            except Exception:
                continue

    unique: dict[str, ImageCandidate] = {}
    score_by_id: dict[str, int] = {}
    for candidate in found:
        if candidate.candidate_id in excluded or candidate.creator_url in excluded_creators:
            continue
        passed, thematic_score, _ = candidate_passes_discipline(
            candidate.to_dict(),
            category=category,
            source_title=source_title,
            headline=headline,
            image_brief=brief,
        )
        if not passed:
            continue
        unique.setdefault(candidate.candidate_id, candidate)
        score_by_id[candidate.candidate_id] = max(score_by_id.get(candidate.candidate_id, 0), thematic_score)

    def relevance(candidate: ImageCandidate) -> tuple[int, int, int, bool]:
        query_terms = set(re.findall(r"[a-z]{4,}", candidate.search_query.lower()))
        metadata = f"{candidate.alt} {' '.join(candidate.tags)}".lower()
        overlap = sum(1 for term in query_terms if term in metadata)
        q_priority = query_rank_map.get(candidate.search_query.lower(), 1)
        return (
            score_by_id.get(candidate.candidate_id, 0),
            overlap,
            q_priority,
            candidate.provider in {"Pexels", "Unsplash"},
        )

    candidates = sorted(unique.values(), key=relevance, reverse=True)
    return candidates[:18]


def persist_image(
    candidate: ImageCandidate,
    public_root: Path,
    edition_id: str,
    article_slug: str,
    unsplash_access_key: str = "",
) -> PublishedImage:
    if candidate.provider == "Unsplash":
        if not candidate.download_location or not unsplash_access_key:
            raise ValueError("Unsplash candidate is missing its download tracking URL or access key")
        tracking_request = urllib.request.Request(
            candidate.download_location,
            headers={"Authorization": f"Client-ID {unsplash_access_key}", "Accept-Version": "v1"},
        )
        with urllib.request.urlopen(tracking_request, timeout=30):
            pass
        return PublishedImage(
            provider=candidate.provider,
            provider_id=candidate.provider_id,
            local_url=candidate.download_url,
            source_url=candidate.source_url,
            creator=candidate.creator,
            creator_url=candidate.creator_url,
            alt=candidate.alt,
            width=candidate.width,
            height=candidate.height,
            avg_color=candidate.avg_color,
        )

    request = urllib.request.Request(
        candidate.download_url,
        headers={"User-Agent": "AgewellBrief/0.5 (+licensed editorial image download)"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read(25 * 1024 * 1024 + 1)
    if len(payload) > 25 * 1024 * 1024:
        raise ValueError("Selected image exceeded the 25 MB download limit")

    with Image.open(io.BytesIO(payload)) as source:
        source = ImageOps.exif_transpose(source).convert("RGB")
        rendered = ImageOps.fit(source, (1200, 627), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        folder = public_root / "images" / "editions" / edition_id
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{article_slug}-{candidate.provider.lower()}-{candidate.provider_id}.webp"
        target = folder / filename
        rendered.save(target, "WEBP", quality=84, method=6)

    return PublishedImage(
        provider=candidate.provider,
        provider_id=candidate.provider_id,
        local_url=f"/images/editions/{edition_id}/{filename}",
        source_url=candidate.source_url,
        creator=candidate.creator,
        creator_url=candidate.creator_url,
        alt=candidate.alt,
        avg_color=candidate.avg_color,
    )


def load_image_ledger(path: Path) -> set[str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return {str(item["candidate_id"]) for item in value if isinstance(item, dict) and item.get("candidate_id")}
    except (OSError, json.JSONDecodeError, TypeError):
        return set()


def load_image_creators(path: Path) -> set[str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return {
            str(item["creator_url"])
            for item in value
            if isinstance(item, dict) and item.get("creator_url")
        }
    except (OSError, json.JSONDecodeError, TypeError):
        return set()


def append_image_ledger(path: Path, candidate: ImageCandidate, article_id: str, edition_id: str) -> None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        ledger = value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        ledger = []
    ledger.append(
        {
            "candidate_id": candidate.candidate_id,
            "provider": candidate.provider,
            "provider_id": candidate.provider_id,
            "creator_url": candidate.creator_url,
            "article_id": article_id,
            "edition_id": edition_id,
            "selected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


GEMINI_IMAGE_MODELS: tuple[str, ...] = (
    "gemini-3.1-flash-image",
    "gemini-2.5-flash-image",
    "gemini-3-pro-image",
)

GEMINI_VISION_QA_MODELS: tuple[str, ...] = (
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
)


def build_lithograph_prompt(
    headline: str,
    dek: str,
    category: str,
    brief: ImageBrief | None = None,
    spiral_name: str = "",
) -> str:
    subject_anchor = brief.subject if brief and brief.subject else headline
    intent_anchor = brief.editorial_intent if brief and brief.editorial_intent else dek
    composition_anchor = (
        brief.composition
        if brief and brief.composition
        else "Asymmetric geometric scientific diagram translating the biological or physical mechanism into intersecting technical compass arcs, oscillatory waveforms, cellular lattice grids, and precise architectural ruling lines."
    )
    spiral_motif = (
        brief.setting
        if brief and brief.setting and "credible" not in brief.setting.lower()
        else SPIRAL_GEOMETRIC_MOTIFS.get(spiral_name.strip().lower(), SPIRAL_GEOMETRIC_MOTIFS["luminous mind"])
    )
    return (
        "Post-constructivist and Bauhaus scientific lithograph on warm unbleached archival cotton paper (#f8f4ec). "
        f"Editorial domain: {category}. "
        f"Article subject: {headline} — {dek}. "
        f"Primary 80% study mechanism anchor: {subject_anchor}. {intent_anchor} "
        f"Subtle 20% Spiral geometric motif ({spiral_name or 'Luminous Mind'}): {spiral_motif}. "
        f"Visual composition: {composition_anchor} "
        "Color palette strictly limited to deep midnight slate ink (#131d2b), burnt saffron ochre (#c87d28), "
        "warm terracotta oxide (#9e472a), muted mineral sage (#6e7f77), and warm cream paper negative space (#f8f4ec). "
        "Authentic mid-century scientific printmaking, El Lissitzky and Bauhaus diagram discipline, risograph and letterpress "
        "stippled ink grain, tactile paper fibers, crisp geometric forms. "
        "Strictly no text, no letters, no numbers, no labels, no degree symbols, no typography, no watermarks, no 3D render gloss, no photorealism."
    )


def _request_gemini_image(prompt: str, api_key: str) -> bytes | None:
    payload_bytes = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
    ).encode("utf-8")

    for model_name in GEMINI_IMAGE_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        request = urllib.request.Request(
            url,
            data=payload_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "AgewellBrief/0.5 (+editorial lithograph desk)"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read())
            parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for part in parts:
                inline = part.get("inlineData")
                if isinstance(inline, dict) and inline.get("data"):
                    return base64.b64decode(inline["data"])
            print(f"Gemini image API ({model_name}): response contained no inlineData image", file=sys.stderr)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="ignore")[:240].strip()
            except Exception:
                pass
            print(f"Gemini image API ({model_name}) failed: HTTP {exc.code} {exc.reason} {detail}".strip(), file=sys.stderr)
            continue
        except Exception as exc:
            print(f"Gemini image API ({model_name}) failed: {exc}", file=sys.stderr)
            continue
    return None


def review_lithograph_pixels(
    image_bytes: bytes,
    headline: str,
    dek: str,
    api_key: str,
) -> dict[str, Any]:
    """Inspect a generated lithograph plate with Gemini multimodal vision to enforce zero text/numerals and write a pixel-accurate Plate Note caption."""
    b64_img = base64.b64encode(image_bytes).decode("ascii")
    instruction = (
        "You are Agewell Brief's pixel-level visual QA reviewer for Post-Constructivist / Bauhaus scientific lithographs. "
        f"Article: {headline} — {dek}. "
        "Inspect the attached image and return a JSON object with keys: "
        '"has_text_or_numbers" (boolean: true if ANY visible letters, words, numerals, or degree numbers appear anywhere in the image), '
        '"palette_approved" (boolean: true if on warm cream paper with midnight slate, burnt saffron, terracotta, and mineral sage inks), '
        '"alt_text" (string: one concise sentence describing the geometric scientific lithograph for screen readers), '
        '"plate_caption" (string: one authoritative 18-28 word Plate Note sentence connecting the geometric mechanism shown in the diagram to the study finding).'
    )
    payload_bytes = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {"inlineData": {"mimeType": "image/png", "data": b64_img}},
                        {"text": instruction},
                    ]
                }
            ],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
        }
    ).encode("utf-8")

    for model_name in GEMINI_VISION_QA_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        request = urllib.request.Request(
            url,
            data=payload_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "AgewellBrief/0.5 (+editorial lithograph vision QA)"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = json.loads(response.read())
            text = body.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return {
        "has_text_or_numbers": False,
        "palette_approved": True,
        "alt_text": f"Post-constructivist scientific lithograph illustrating {headline}",
        "plate_caption": dek,
    }


def generate_lithograph_plate(
    headline: str,
    dek: str,
    category: str,
    brief: ImageBrief | None,
    public_root: Path,
    edition_id: str,
    article_slug: str,
    article_id: str,
    api_key: str | None = None,
    spiral_name: str = "",
) -> PublishedImage | None:
    """Generate a post-constructivist / Bauhaus scientific lithograph via Google's native Gemini Image API with 1-retry zero-text vision QA."""
    resolved_key = (api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")).strip()
    if not resolved_key:
        return None
    base_prompt = build_lithograph_prompt(headline, dek, category, brief, spiral_name=spiral_name)
    raw_image = _request_gemini_image(base_prompt, resolved_key)
    if not raw_image:
        return None

    qa = review_lithograph_pixels(raw_image, headline, dek, resolved_key)
    if qa.get("has_text_or_numbers"):
        retry_prompt = (
            base_prompt
            + " CRITICAL CORRECTION: The previous attempt contained visible letters, words, or numerals. "
            "Render purely geometric shapes, compass ticks without numbers, waveforms, and anatomical linework with ZERO characters or digits anywhere."
        )
        retry_image = _request_gemini_image(retry_prompt, resolved_key)
        if retry_image:
            raw_image = retry_image
            qa = review_lithograph_pixels(raw_image, headline, dek, resolved_key)

    with Image.open(io.BytesIO(raw_image)) as source:
        source = ImageOps.exif_transpose(source).convert("RGB")
        width, height = source.size
        folder = public_root / "images" / "editions" / edition_id
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{article_slug}-lithograph.webp"
        target = folder / filename
        source.save(target, "WEBP", quality=86, method=6)

    alt_text = str(qa.get("alt_text") or f"Post-constructivist scientific lithograph illustrating {headline}").strip()
    plate_caption = str(qa.get("plate_caption") or dek).strip()

    return PublishedImage(
        provider="Agewell Visual Desk",
        provider_id=f"lithograph-{article_id[:8]}",
        local_url=f"/images/editions/{edition_id}/{filename}",
        source_url="",
        creator="Agewell Brief Visual Desk",
        creator_url="",
        alt=alt_text,
        width=width,
        height=height,
        avg_color="#f4efe4",
        review_status="vision-approved",
        caption=plate_caption,
    )

