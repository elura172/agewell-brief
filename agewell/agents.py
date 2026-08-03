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


def _deterministic_novelty(title: str, summary: str, source: str = "") -> dict[str, Any]:
    """Conservative fallback for when the novelty editor is unavailable."""
    text = f"{title} {summary}".lower()
    score = 48
    reasons: list[str] = []
    frontier_terms = (
        "senescen", "biomarker", "first-in-human", "first in human", "new tool",
        "new test", "wearable", "brain-computer", "single-cell", "spatial",
        "organoid", "gene editing", "machine learning", "artificial intelligence",
        "quantum", "mitochond", "microbiome", "clinical trial", "randomized",
        "fda warning", "recall", "unexpected", "overturn", "discovered why",
    )
    generic_terms = (
        "hours a night", "may help slow aging", "healthy aging", "linked to",
        "associated with", "could help", "tips", "simple ways", "eat less",
        "sleep duration", "drink more water",
    )
    frontier_hits = [term for term in frontier_terms if term in text]
    generic_hits = [term for term in generic_terms if term in text]
    if frontier_hits:
        score += min(30, 10 * len(frontier_hits))
        reasons.append("specific frontier signal or meaningful new mechanism")
    if generic_hits:
        score -= min(32, 10 * len(generic_hits))
        reasons.append("familiar wellness framing with limited editorial surprise")
    if re.search(r"\b(first|new|unexpected|reveals|why|challenge|warning|recall)\b", text):
        score += 8
        reasons.append("headline contains a concrete news hook")
    if re.search(r"\b\d+(?:\.\d+)?%|\b\d+[-–]\d+\b|\b\d+ participants\b", text):
        score += 5
        reasons.append("specific result or population detail")
    if "arxiv.org" in source or "biorxiv" in source or "medrxiv" in source:
        score += 5
        reasons.append("frontier source deserves contextual reporting")
    score = max(0, min(100, score))
    decision = "commission" if score >= 58 else "hold"
    return {
        "score": score,
        "decision": decision,
        "novelty_type": "frontier_signal" if frontier_hits else "contextual_update",
        "reason": "; ".join(dict.fromkeys(reasons)) or "No strong novelty signal detected.",
        "angle": "Report the specific change, mechanism, or consequence rather than repeating generic advice.",
        "mode": "deterministic_fallback",
    }


def novelty_editor(
    client: Any,
    model: str,
    candidates: list[Any],
    trend_topics: list[dict[str, Any]],
    recent_titles: list[str],
    minimum_score: int = 58,
) -> dict[str, Any]:
    """Score whether a candidate has enough novelty to earn a draft."""
    rows = [
        {
            "article_id": article_id(item.link),
            "title": item.title,
            "summary": item.summary[:1200],
            "source": item.source_name,
            "link": item.link,
            "category": item.source_group,
        }
        for item in candidates
    ]
    fallback = {
        row["article_id"]: _deterministic_novelty(row["title"], row["summary"], row["link"])
        for row in rows
    }
    if not rows:
        return {"scores": {}, "commissioned_ids": [], "held_back": [], "mode": "fallback"}
    try:
        result = _json_response(
            client,
            model,
            "You are Agewell Brief's novelty editor. Protect the reader's attention. Return JSON only.",
            {
                "candidates": rows,
                "trend_topics": trend_topics[:25],
                "recent_titles": recent_titles[-40:],
                "requirements": [
                    "Score every candidate from 0 to 100 for editorial novelty and reader-stop power.",
                    "A story earns a high score for a specific new finding, named mechanism, unusual result, meaningful disagreement, frontier technology, safety warning, or genuinely useful change in practice.",
                    "Score down generic advice, routine observational associations, broad lifestyle reminders, recycled supplement claims, and headlines that could have run any year.",
                    "Do not confuse scientific importance with novelty. A familiar true fact can still be held back.",
                    f"Recommend commission at {minimum_score}+; hold anything below that unless it is a major safety or public-interest story.",
                    "Return one score object per article_id with score, decision, novelty_type, reason, and a sharper possible angle.",
                ],
                "output_schema": {"scores": [{"article_id": "...", "score": 0, "decision": "commission|hold", "novelty_type": "...", "reason": "...", "angle": "..."}]},
            },
            2200,
        )
        scored: dict[str, dict[str, Any]] = {}
        valid_ids = set(fallback)
        for value in result.get("scores", []):
            if not isinstance(value, dict) or value.get("article_id") not in valid_ids:
                continue
            key = str(value["article_id"])
            score = max(0, min(100, int(value.get("score", 0))))
            scored[key] = {
                "score": score,
                "decision": "commission" if score >= minimum_score else "hold",
                "novelty_type": str(value.get("novelty_type") or "contextual_update")[:80],
                "reason": str(value.get("reason") or "No reason supplied.")[:500],
                "angle": str(value.get("angle") or "Find the specific change or consequence.")[:400],
                "mode": "agent",
            }
        if len(scored) != len(rows):
            raise ValueError("novelty editor did not score every candidate")
        scores = scored
        mode = "agent"
    except Exception as exc:
        scores = fallback
        mode = "deterministic_fallback"
        error = str(exc)
    commissioned = [key for key, value in scores.items() if value["score"] >= minimum_score]
    held_back = [key for key, value in scores.items() if key not in commissioned]
    output = {"scores": scores, "commissioned_ids": commissioned, "held_back": held_back, "mode": mode}
    if mode != "agent":
        output["error"] = error
    return output


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
        preserved_fields = []
        result["bullets"] = result.get("bullets", original["bullets"])
        if len(result["bullets"]) != 3:
            raise ValueError("copy editor changed bullet count")
        if "sections" in original:
            if len(result.get("sections", [])) != len(original["sections"]):
                result["sections"] = original["sections"]
                preserved_fields.append("sections")
        for key in ("headline", "dek", "caveat"):
            if not str(result.get(key, "")).strip():
                result[key] = original[key]
                preserved_fields.append(key)
        return result, {"status": "approved", "changed": result != original, "preserved_fields": preserved_fields}
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
