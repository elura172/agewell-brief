from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


CLICKBANK_ERROR_MARKERS = (
    "clickbank: hoplink error",
    "hoplink error",
    "affiliate is not approved",
    "affiliate has not been approved",
    "not authorized to promote",
)
BLOCKING_HEALTH_STATUSES = {"invalid", "hoplink_error"}


@dataclass(frozen=True)
class AffiliateOffer:
    category: str
    url: str
    name: str = "ClickBank offer"
    approved: bool = True
    priority: int = 0

    @property
    def offer_id(self) -> str:
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class OfferHealth:
    offer_id: str
    category: str
    name: str
    status: str
    http_status: int | None = None
    final_host: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_clickbank_hoplink(value: str) -> bool:
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        hostname == "hop.clickbank.net" or hostname.endswith(".hop.clickbank.net")
    )


def parse_offer_config(configured: dict[str, Any]) -> list[AffiliateOffer]:
    """Normalize legacy category mappings and the richer reviewed-offer format.

    Legacy configuration remains supported::

        {"mobility": "https://encrypted.hop.clickbank.net"}

    For several offers or explicit approval state, use::

        {"offers": [{"category": "mobility", "url": "...", "approved": true}]}
    """
    normalized: list[AffiliateOffer] = []
    raw_offers = configured.get("offers") if isinstance(configured, dict) else None
    if isinstance(raw_offers, list):
        for value in raw_offers:
            if not isinstance(value, dict):
                continue
            category = str(value.get("category", "")).strip().lower()
            url = str(value.get("url", "")).strip()
            if not category or not url:
                continue
            normalized.append(
                AffiliateOffer(
                    category=category,
                    url=url,
                    name=str(value.get("name") or "ClickBank offer").strip(),
                    approved=value.get("approved") is True,
                    priority=int(value.get("priority", 0)),
                )
            )
        return normalized

    if not isinstance(configured, dict):
        return []
    for category, value in configured.items():
        if isinstance(value, str):
            normalized.append(AffiliateOffer(str(category).strip().lower(), value.strip()))
            continue
        if not isinstance(value, list):
            continue
        for entry in value:
            if isinstance(entry, str):
                normalized.append(AffiliateOffer(str(category).strip().lower(), entry.strip()))
            elif isinstance(entry, dict) and entry.get("url"):
                normalized.append(
                    AffiliateOffer(
                        category=str(category).strip().lower(),
                        url=str(entry["url"]).strip(),
                        name=str(entry.get("name") or "ClickBank offer").strip(),
                        approved=entry.get("approved") is True,
                        priority=int(entry.get("priority", 0)),
                    )
                )
    return normalized


def load_health_status(path: Path) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries = payload.get("offers", []) if isinstance(payload, dict) else []
    return {
        str(entry["offer_id"]): str(entry["status"])
        for entry in entries
        if isinstance(entry, dict) and entry.get("offer_id") and entry.get("status")
    }


def select_offer(
    configured: dict[str, Any],
    category: str,
    article_id: str = "",
    health_status: dict[str, str] | None = None,
) -> str | None:
    """Choose one approved, technically usable offer for an exact category.

    Equal-priority offers are distributed deterministically by article ID, so
    the same article always receives the same destination.
    """
    health = health_status or {}
    candidates = [
        offer
        for offer in parse_offer_config(configured)
        if offer.category == category.lower()
        and offer.approved
        and is_clickbank_hoplink(offer.url)
        and health.get(offer.offer_id) not in BLOCKING_HEALTH_STATUSES
    ]
    if not candidates:
        return None
    top_priority = max(offer.priority for offer in candidates)
    finalists = sorted(
        (offer for offer in candidates if offer.priority == top_priority),
        key=lambda offer: (offer.name.lower(), offer.offer_id),
    )
    seed = hashlib.sha256((article_id or category).encode("utf-8")).digest()
    return finalists[int.from_bytes(seed[:4], "big") % len(finalists)].url


def tracked_offer_url(base_url: str | None, category: str, article_id: str) -> str | None:
    """Append a stable ClickBank tracking ID without altering the HopLink."""
    if not base_url:
        return None
    if not is_clickbank_hoplink(base_url):
        raise ValueError(f"Affiliate offer is not a valid HTTPS ClickBank HopLink: {base_url}")

    parsed = urlsplit(base_url)
    category_token = re.sub(r"[^a-z0-9_]+", "_", category.lower()).strip("_")[:32]
    article_token = re.sub(r"[^a-z0-9_]+", "", article_id.lower())[:24]
    tid = f"agewell_{category_token}_{article_token}"[:100]
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["tid"] = tid
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def check_offer(offer: AffiliateOffer, timeout: int = 25) -> OfferHealth:
    if not is_clickbank_hoplink(offer.url):
        return OfferHealth(offer.offer_id, offer.category, offer.name, "invalid", detail="Invalid ClickBank HopLink")
    probe_url = tracked_offer_url(offer.url, offer.category, "linkcheck") or offer.url
    request = urllib.request.Request(
        probe_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AgewellBrief/1.0; +https://agewellbrief.com/about)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(512 * 1024).decode("utf-8", errors="ignore").lower()
            final_host = (urlsplit(response.geturl()).hostname or "").lower()
            status = int(getattr(response, "status", 200))
        if any(marker in body for marker in CLICKBANK_ERROR_MARKERS):
            return OfferHealth(
                offer.offer_id,
                offer.category,
                offer.name,
                "hoplink_error",
                status,
                final_host,
                "ClickBank returned a HopLink or approval error page",
            )
        return OfferHealth(offer.offer_id, offer.category, offer.name, "reachable", status, final_host)
    except urllib.error.HTTPError as exc:
        return OfferHealth(
            offer.offer_id,
            offer.category,
            offer.name,
            "unreachable",
            exc.code,
            (urlsplit(exc.geturl()).hostname or "").lower(),
            f"HTTP {exc.code}; attribution still requires a manual ClickBank test",
        )
    except (OSError, ValueError) as exc:
        return OfferHealth(
            offer.offer_id,
            offer.category,
            offer.name,
            "unreachable",
            detail=f"{type(exc).__name__}: {exc}",
        )


def write_health_report(path: Path, configured: dict[str, Any]) -> dict[str, Any]:
    checks = [check_offer(offer) for offer in parse_offer_config(configured) if offer.approved]
    report = {
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "note": "Technical reachability is not proof of affiliate attribution; verify each approved offer once in ClickBank.",
        "offers": [check.to_dict() for check in checks],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
