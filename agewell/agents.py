"""Small, auditable editorial desk agents used by the publishing pipeline."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any


def article_id(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()[:24]


def _json_response(client: Any, model: str, system: str, payload: dict[str, Any], max_tokens: int) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload)}],
        extra_body={"thinking": {"type": "disabled"}},
    )
    value = json.loads(response.choices[0].message.content or "{}")
    if not isinstance(value, dict):
        raise ValueError("agent response was not an object")
    return value


def assignment_editor(
    client: Any,
    model: str,
    candidates: list[Any],
    trend_topics: list[dict[str, Any]],
    recent_titles: list[str],
    limit: int,
) -> dict[str, Any]:
    """Select an edition lineup; fall back to deterministic candidate order."""
    candidate_rows = [
        {
            "article_id": article_id(item.link),
            "title": item.title,
            "summary": item.summary[:900],
            "source": item.source_name,
            "category": item.source_group,
            "link": item.link,
        }
        for item in candidates
    ]
    fallback = [
        {"article_id": row["article_id"], "role": "lead" if index == 0 else "signal", "angle": "Explain what this means for readers over 50.", "confidence": 0.5}
        for index, row in enumerate(candidate_rows[:limit])
    ]
    if not candidates:
        return {"edition_angle": "No suitable stories found.", "assignments": [], "held_back": [], "mode": "fallback"}
    try:
        result = _json_response(
            client,
            model,
            "You are Agewell Brief's assignment editor. Select stories, do not invent facts, and return JSON only.",
            {
                "candidates": candidate_rows,
                "trend_topics": trend_topics[:25],
                "recent_titles": recent_titles[-40:],
                "requirements": [
                    f"Select at most {limit} stories.",
                    "Choose one lead and make the rest signals.",
                    "Prefer source diversity and a mix of categories.",
                    "Prioritize fresh, independently corroborated trend topics.",
                    "Reject duplicates and stories too weak to explain responsibly.",
                    "Every assignment must use an article_id from candidates.",
                ],
            },
            1800,
        )
        assignments = result.get("assignments")
        valid_ids = {row["article_id"] for row in candidate_rows}
        if not isinstance(assignments, list):
            raise ValueError("assignments must be a list")
        cleaned = []
        seen = set()
        for entry in assignments:
            if not isinstance(entry, dict) or entry.get("article_id") not in valid_ids:
                continue
            key = entry["article_id"]
            if key in seen:
                continue
            seen.add(key)
            cleaned.append({
                "article_id": key,
                "role": "lead" if not any(row["role"] == "lead" for row in cleaned) else "signal",
                "angle": str(entry.get("angle") or "Explain what this means for readers over 50.")[:300],
                "confidence": float(entry.get("confidence", 0.5)),
                "reason": str(entry.get("reason") or "Selected for relevance and freshness.")[:400],
            })
        if not cleaned:
            raise ValueError("agent selected no valid candidates")
        return {
            "edition_angle": str(result.get("edition_angle") or "What matters in health today")[:300],
            "assignments": cleaned[:limit],
            "held_back": result.get("held_back", []),
            "mode": "agent",
        }
    except Exception as exc:
        return {"edition_angle": "What matters in health today", "assignments": fallback, "held_back": [], "mode": "fallback", "error": str(exc)}


def copy_edit(client: Any, model: str, content: dict[str, Any], source_title: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Improve prose while preserving the draft's factual structure."""
    original = copy.deepcopy(content)
    try:
        result = _json_response(
            client,
            model,
            "You are a careful health-publication copy editor. Improve clarity and rhythm without adding facts. Return JSON only.",
            {
                "source_title": source_title,
                "draft": content,
                "rules": [
                    "Preserve the headline's factual meaning, all caveats, and exactly three bullets.",
                    "Preserve exactly four lead sections when sections are present.",
                    "Do not add medical advice, claims, quotations, studies, or product promises.",
                    "Use clear, spirited, warm prose for readers over 50; do not make it childish.",
                ],
            },
            2600,
        )
        result["bullets"] = result.get("bullets", original["bullets"])
        if len(result["bullets"]) != 3:
            raise ValueError("copy editor changed bullet count")
        if "sections" in original and len(result.get("sections", [])) != len(original["sections"]):
            raise ValueError("copy editor changed section count")
        for key in ("headline", "dek", "caveat"):
            if not str(result.get(key, "")).strip():
                raise ValueError(f"copy editor removed {key}")
        return result, {"status": "approved", "changed": result != original}
    except Exception as exc:
        return original, {"status": "fallback", "changed": False, "error": str(exc)}


def commercial_integrity(category: str, offer_urls: list[str]) -> dict[str, Any]:
    issues = []
    if len(offer_urls) > 3:
        issues.append("more than three affiliate links")
    if any("hop.clickbank.net" not in url for url in offer_urls):
        issues.append("non-ClickBank affiliate URL detected")
    return {"status": "approved" if not issues else "held", "category": category, "offer_count": len(offer_urls), "issues": issues}


def release_manager(source_url: str, content: dict[str, Any], offer_review: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    if not source_url.startswith("https://"):
        reasons.append("source URL is not HTTPS")
    if not content.get("headline") or not content.get("dek"):
        reasons.append("headline or dek missing")
    if len(content.get("bullets", [])) != 3:
        reasons.append("exactly three bullets required")
    if offer_review.get("status") != "approved":
        reasons.extend(offer_review.get("issues", []))
    return {"status": "ready_for_human_review" if not reasons else "held", "reasons": reasons}
