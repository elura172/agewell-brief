from __future__ import annotations

import concurrent.futures
import datetime as dt
import io
import json
import re
import threading
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlencode

from PIL import Image, ImageOps

from agewell.editorial import ImageBrief


PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
PIXABAY_SEARCH_URL = "https://pixabay.com/api/"


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
            )
        )
    return candidates


def search_image_candidates(
    brief: ImageBrief,
    pexels_key: str,
    pixabay_key: str,
    cache: ImageSearchCache,
    excluded_ids: set[str] | None = None,
) -> list[ImageCandidate]:
    query = brief.search_queries[0]
    excluded = excluded_ids or set()
    providers: list[tuple[str, str, Callable[[str, str], list[ImageCandidate]]]] = [
        ("Pexels", pexels_key, search_pexels),
        ("Pixabay", pixabay_key, search_pixabay),
    ]

    def load(provider: str, key: str, search: Callable[[str, str], list[ImageCandidate]]) -> list[ImageCandidate]:
        cached = cache.get(provider, query)
        if cached is not None:
            return cached
        found = search(key, query)
        cache.set(provider, query, found)
        return found

    found: list[ImageCandidate] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(load, provider, key, search) for provider, key, search in providers if key]
        for future in concurrent.futures.as_completed(futures):
            try:
                found.extend(future.result())
            except Exception:
                continue

    candidates = [candidate for candidate in found if candidate.candidate_id not in excluded]
    candidates.sort(key=lambda candidate: (candidate.width * candidate.height, candidate.provider == "Pixabay"), reverse=True)
    return candidates[:12]


def persist_image(candidate: ImageCandidate, public_root: Path, edition_id: str, article_slug: str) -> PublishedImage:
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
            "article_id": article_id,
            "edition_id": edition_id,
            "selected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
