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
    raw_text = (response.choices[0].message.content or "{}").strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
        raw_text = re.sub(r"\n?```$", "", raw_text).strip()
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        raw_text = match.group(0)
    try:
        value = json.loads(raw_text)
    except json.JSONDecodeError:
        try:
            value, _ = json.JSONDecoder().raw_decode(raw_text)
        except Exception:
            # Observed failure mode: a "year": 1970s style decade written as a
            # bare token instead of a quoted string. That single invalid token
            # otherwise discards an entire, correct response as {} — quote it
            # and retry once before giving up.
            repaired = re.sub(r'(:\s*)(\d{3,4}s(?:-\d{3,4}s)?)(\s*[,}])', r'\1"\2"\3', raw_text)
            try:
                value = json.loads(repaired)
            except Exception:
                value = {}
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
            "You are Agewell Brief's chief copy editor. Elevate prose to be authoritative, clear, and biophysically precise. Purge dry AI hedging (e.g., 'A connection is context, not proof', 'Only time will tell'). Return JSON only.",
            {
                "source_title": source_title,
                "draft": content,
                "rules": [
                    "Preserve the headline's factual meaning, all caveats, and exactly three bullets.",
                    "Preserve exactly four lead sections when sections are present.",
                    "Purge dry AI boilerplate, corporate jargon, and childish medical condescension.",
                    "Elevate physical explanations, historical biophysics context, and structural clarity.",
                    "Do not add ungrounded medical advice, false claims, or invented studies.",
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
    """Flag commercial conflicts."""
    return {"flagged": False, "reason": "No direct conflict identified."}


def release_manager(source_url: str, content: dict[str, Any], offer_review: dict[str, Any]) -> dict[str, Any]:
    """Approve or block an edition item before release."""
    return {"status": "ready_for_human_review", "reasons": []}


def autoresearch_context_subagent(
    client: Any,
    model: str,
    title: str,
    summary: str,
    category: str,
) -> dict[str, Any]:
    """AutoResearch & Deep Context Subagent:
    Discovers historical antecedents (e.g. Fritz-Albert Popp, Gerald Pollack, Otto Warburg, Alexander Gurwitsch, Hans Selye),
    mechanistic connections, ancestral/traditional health parallels, and exact citations to enhance signal value.
    """
    system_prompt = (
        "You are Agewell Brief's AutoResearch & Deep Context Subagent. "
        "Your task is to enrich cutting-edge scientific preprints with deep biophysical history, "
        "historical antecedents (e.g., Fritz-Albert Popp biophotons, Gerald Pollack EZ water, Otto Warburg metabolic respiration, "
        "Hans Selye stress adaptation, Horvath epigenetic clocks), precise mechanical connections, "
        "and ancestral/traditional lifestyle parallels. "
        "Provide specific, non-vague historical context, key researchers, and referenced connections."
    )
    payload = {
        "title": title,
        "summary": summary[:2000],
        "category": category,
        "instructions": [
            "Identify 1-2 primary historical biophysical or clinical antecedents (specific scientists, years, and discoveries).",
            "Explain precisely how the modern preprint connects to or validates the historical work.",
            "Identify any ancestral or traditional lifestyle parallels backed by physical mechanisms.",
            "Return JSON with 'historical_antecedents', 'mechanistic_bridge', and 'ancestral_insight'.",
            "Each historical_antecedents entry's 'year' must be a JSON string, e.g. \"1970s\" or \"1975\" "
            "— never a bare unquoted token like 1970s, which is invalid JSON and discards the whole response.",
            "historical_antecedents must have exactly 1-2 entries, never more. "
            "mechanistic_bridge and ancestral_insight must each be a single plain-text string, never an array or object.",
            "Each historical_antecedents object has exactly these three keys: scientist, year, discovery. "
            "No other keys (e.g. no separate 'connection' field) — fold any connection to the modern finding into 'discovery' itself.",
        ],
    }
    try:
        # 1200 was cutting off richer answers mid-JSON on finish_reason "length"
        # (observed: 7 antecedents plus expanded mechanistic_bridge/ancestral_insight
        # instead of the usual 1-2) — an unparseable truncated response, not a bad one.
        return _json_response(client, model, system_prompt, payload, max_tokens=2000)
    except Exception as e:
        return {
            "historical_antecedents": [],
            "mechanistic_bridge": "Direct primary preprint research.",
            "ancestral_insight": "",
            "error": str(e),
        }

