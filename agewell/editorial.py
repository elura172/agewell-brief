from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from openai import OpenAI


@dataclass(frozen=True)
class EvidencePacket:
    study_type: str
    key_claims: tuple[str, ...]
    limitations: tuple[str, ...]
    what_not_to_say: tuple[str, ...]
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImageBrief:
    editorial_intent: str
    subject: str
    setting: str
    mood: str
    composition: str
    avoid: tuple[str, ...]
    search_queries: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AlignmentReview:
    selected_candidate_id: str
    score: int
    rationale: str
    concerns: tuple[str, ...]
    metadata_status: str = "approved"
    visual_status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VisionReviewer(Protocol):
    def review(
        self,
        image_path: str,
        image_brief: ImageBrief,
        story: dict[str, Any],
    ) -> dict[str, Any]: ...


class DeferredVisionReviewer:
    """Explicit seam for a future image-capable model.

    DeepSeek currently directs and proofreads from text metadata. This reviewer
    refuses to pretend that metadata inspection is pixel-level vision.
    """

    def review(
        self,
        image_path: str,
        image_brief: ImageBrief,
        story: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "status": "pending",
            "reviewer": "deferred-vision-interface",
            "image_path": image_path,
            "reason": "Pixel-level vision review is not configured yet.",
        }


def _json_agent(
    client: OpenAI,
    model: str,
    system_prompt: str,
    payload: dict[str, Any],
    max_tokens: int,
) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        temperature=0.15,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": f"{system_prompt}\nReturn exactly one valid JSON object and no surrounding text."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        extra_body={"thinking": {"type": "disabled"}},
    )
    value = json.loads(response.choices[0].message.content or "{}")
    if not isinstance(value, dict):
        raise ValueError("Agent response was not a JSON object")
    return value


def build_evidence_packet(
    client: OpenAI,
    model: str,
    source_title: str,
    source_summary: str,
    source_material: str,
    source_url: str,
) -> EvidencePacket:
    payload = {
        "source_title": source_title,
        "source_summary": source_summary[:5000],
        "source_material": source_material[:18000],
        "source_url": source_url,
        "output": {
            "study_type": "short plain-language label",
            "key_claims": "3-6 source-supported claims",
            "limitations": "1-4 limits, uncertainties, or missing context",
            "what_not_to_say": "claims the source does not justify",
            "confidence": "high, moderate, limited, or unclear",
        },
    }
    result = _json_agent(
        client,
        model,
        (
            "You are Agewell Brief's evidence analyst. Extract only what the supplied source supports. "
            "Do not add medical guidance, causal language, institutions, numbers, or study details that are absent."
        ),
        payload,
        1400,
    )
    claims = tuple(str(value).strip() for value in result.get("key_claims", []) if str(value).strip())
    limitations = tuple(str(value).strip() for value in result.get("limitations", []) if str(value).strip())
    forbidden = tuple(str(value).strip() for value in result.get("what_not_to_say", []) if str(value).strip())
    if not claims:
        claims = (source_summary.strip() or source_title.strip(),)
    return EvidencePacket(
        study_type=str(result.get("study_type", "reported health research")).strip(),
        key_claims=claims[:6],
        limitations=limitations[:4],
        what_not_to_say=forbidden[:5],
        confidence=str(result.get("confidence", "unclear")).strip().lower(),
    )


def direct_image(
    client: OpenAI,
    model: str,
    source_title: str,
    category: str,
    story: dict[str, Any],
) -> ImageBrief:
    payload = {
        "source_title": source_title,
        "category": category,
        "story": story,
        "requirements": [
            "Direct an editorial photograph, not an advertisement or literal medical promise.",
            "Prefer human situations, research environments, movement, food, or place when genuinely relevant.",
            "Avoid frightened expressions, disability stereotypes, pills in hands, miracle imagery, and generic retirement poses.",
            "Return exactly three concrete stock-photo search queries, each 3-8 words.",
            "Queries must describe visible subjects and settings, not abstract concepts.",
        ],
    }
    result = _json_agent(
        client,
        model,
        "You are the image director for a spirited, credible health publication for adults in later life.",
        payload,
        1000,
    )
    queries = tuple(str(value).strip() for value in result.get("search_queries", []) if str(value).strip())
    if not queries:
        queries = (f"{category} healthy daily life", "health research natural light", "active adult everyday life")
    avoid = tuple(str(value).strip() for value in result.get("avoid", []) if str(value).strip())
    return ImageBrief(
        editorial_intent=str(result.get("editorial_intent", "Show the story's human relevance without overclaiming.")).strip(),
        subject=str(result.get("subject", "an authentic person or research setting")).strip(),
        setting=str(result.get("setting", "a credible everyday environment")).strip(),
        mood=str(result.get("mood", "alert, capable, and natural")).strip(),
        composition=str(result.get("composition", "landscape editorial framing with a clear focal subject")).strip(),
        avoid=avoid or ("fearful expressions", "miracle-product imagery", "patronizing retirement stereotypes"),
        search_queries=queries[:3],
    )


def review_image_metadata(
    client: OpenAI,
    model: str,
    story: dict[str, Any],
    image_brief: ImageBrief,
    candidates: list[dict[str, Any]],
) -> AlignmentReview:
    if not candidates:
        raise ValueError("No image candidates were supplied")
    payload = {
        "story": story,
        "image_brief": image_brief.to_dict(),
        "candidates": candidates,
        "requirements": [
            "Select one candidate using only supplied title, tags, alt text, dimensions, and attribution metadata.",
            "Do not claim to have seen pixels.",
            "Reject candidates whose metadata suggests fear, products, procedures, or stereotypes not supported by the story.",
            "Return selected_candidate_id, score from 0-100, rationale, and concerns.",
        ],
    }
    result = _json_agent(
        client,
        model,
        "You are Agewell Brief's image-to-story metadata proofreader. Be decisive and explicit about the limits of metadata-only review.",
        payload,
        1000,
    )
    valid_ids = {str(candidate["candidate_id"]) for candidate in candidates}
    selected = str(result.get("selected_candidate_id", ""))
    if selected not in valid_ids:
        selected = str(candidates[0]["candidate_id"])
    concerns = tuple(str(value).strip() for value in result.get("concerns", []) if str(value).strip())
    try:
        score = max(0, min(100, int(result.get("score", 70))))
    except (TypeError, ValueError):
        score = 70
    return AlignmentReview(
        selected_candidate_id=selected,
        score=score,
        rationale=str(result.get("rationale", "Best metadata match among the available candidates.")).strip(),
        concerns=concerns,
    )
