from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from openai import OpenAI


def _string_tuple(value: Any) -> tuple[str, ...]:
    """Normalize model output without accidentally splitting strings into characters."""
    if isinstance(value, str):
        cleaned = value.strip()
        return (cleaned,) if cleaned else ()
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _fallback_image_queries(source_title: str, category: str) -> tuple[str, str, str]:
    title = source_title.lower()
    if any(term in title for term in ("diet", "food", "nutrition", "mediterranean")):
        return ("Mediterranean food preparation", "older adult cooking vegetables", "heart healthy meal ingredients")
    if any(term in title for term in ("supplement", "hidden drug", "product notification", "fraud", "recall")):
        return ("scientists testing supplements laboratory", "pharmacist checking medicine label", "quality control laboratory researchers")
    if any(term in title for term in ("speech", "language", "voice")):
        return ("speech neuroscience research laboratory", "speech therapy assistive technology", "brain researcher computer laboratory")
    if category == "brain health":
        return ("neuroscience researcher brain scan", "brain imaging laboratory researcher", "cognitive research computer laboratory")
    if category == "mobility":
        return ("older adult walking outdoors", "physical therapist mobility session", "strength training older adult")
    if category == "metabolic health":
        return ("metabolic research laboratory", "blood glucose research scientist", "healthy meal preparation adult")
    if category == "consumer safety":
        return ("scientists testing supplements laboratory", "pharmacist checking medicine label", "quality control laboratory researchers")
    if category == "longevity":
        return ("aging research laboratory scientist", "active older adult outdoors", "cell biology research microscope")
    return ("health researcher laboratory", "active adult daily life", "medical research natural light")


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
    claims = _string_tuple(result.get("key_claims", []))
    limitations = _string_tuple(result.get("limitations", []))
    forbidden = _string_tuple(result.get("what_not_to_say", []))
    if not claims:
        claims = (source_summary.strip() or source_title.strip(),)
    return EvidencePacket(
        study_type=str(result.get("study_type", "reported health research")).strip(),
        key_claims=claims[:6],
        limitations=limitations[:4],
        what_not_to_say=forbidden[:5],
        confidence=str(result.get("confidence", "unclear")).strip().lower(),
    )


EVIDENCE_POSITIONS = ("established", "emerging", "contested", "speculative")

# Verbatim from editorial-policy.astro's public Layer 4 badging — the two must
# stay in sync, since this classifier exists to make that public promise true
# rather than the schema default ("emerging") applying to every brief silently.
EVIDENCE_POSITION_RUBRIC = (
    "established: Replicated clinical trials & systematic reviews.\n"
    "emerging: Phase I/II trials, novel animal models, bioRxiv/medRxiv preprints.\n"
    "contested: Conflicting trial data or competing mechanistic hypotheses.\n"
    "speculative: Early theoretical biophysics & preliminary arXiv models."
)


def classify_evidence_position(
    client: OpenAI,
    model: str,
    study_type: str,
    key_claims: tuple[str, ...],
    limitations: tuple[str, ...],
) -> str:
    """Classify a brief's evidence maturity using the same four-category rubric
    already published to readers, rather than leaving every brief at the schema
    default of "emerging" regardless of whether it's a systematic review or a
    single unreplicated preprint.

    Deliberately does NOT use EvidencePacket.confidence as an input: confidence
    describes how clearly THIS ARTICLE stated its claims, not how mature the
    underlying science is — a vague write-up of a landmark systematic review and
    a crisply-written single preprint are different evidence_positions despite
    similar confidence. study_type and the claims themselves are the right axis.
    """
    payload = {
        "study_type": study_type,
        "key_claims": list(key_claims),
        "limitations": list(limitations),
        "rubric": EVIDENCE_POSITION_RUBRIC,
        "output": {"evidence_position": "one of established, emerging, contested, speculative"},
    }
    result = _json_agent(
        client,
        model,
        (
            "You are Agewell Brief's evidence-maturity classifier. Apply the supplied rubric literally: "
            "match the study_type and claims to the closest single category. Do not default to 'emerging' "
            "as a safe middle choice — pick 'established' when the study_type is a systematic review, "
            "meta-analysis, or explicitly replicated trial; pick 'speculative' when the study_type is "
            "theoretical, a preliminary model, or a single early-stage finding with no replication; "
            "pick 'contested' only when limitations or claims describe actual disagreement with prior work."
        ),
        payload,
        200,
    )
    position = str(result.get("evidence_position", "")).strip().lower()
    return position if position in EVIDENCE_POSITIONS else "emerging"


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
        "output": {
            "editorial_intent": "one sentence",
            "subject": "specific visible subject",
            "setting": "specific visible setting",
            "mood": "three concise adjectives",
            "composition": "landscape editorial composition",
            "avoid": "array of visual exclusions",
            "search_queries": "array of exactly three concrete stock-photo queries",
        },
        "requirements": [
            "Direct an editorial photograph, not an advertisement or literal medical promise.",
            "Prefer human situations, research environments, movement, food, or place when genuinely relevant.",
            "Avoid frightened expressions, disability stereotypes, pills in hands, miracle imagery, and generic retirement poses.",
            "Return exactly three concrete stock-photo search queries, each 3-8 words.",
            "Queries must describe visible subjects and settings, not abstract concepts.",
            "At least two queries must use a concrete, visible subject specific to this exact story.",
            "Do not use generic wellness, healthy lifestyle, kitchen, or retirement imagery unless the story is actually about those subjects.",
            "For neuroscience or medical-device stories, prefer relevant labs, scans, researchers, speech therapy, or technology over unrelated lifestyle scenes.",
        ],
    }
    result = _json_agent(
        client,
        model,
        "You are the image director for a spirited, credible health publication for adults in later life.",
        payload,
        1000,
    )
    queries = _string_tuple(result.get("search_queries", []))
    generic_markers = ("healthy daily life", "health research natural light", "active adult everyday life")
    if len(queries) < 3 or any(marker in query.lower() for query in queries for marker in generic_markers):
        queries = _fallback_image_queries(source_title, category)
    avoid = _string_tuple(result.get("avoid", []))
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
            "Reject generic lifestyle imagery when it does not depict the actual subject of the story.",
            "Reject near-duplicate or same-shoot imagery when the candidate metadata identifies that risk.",
            "Return selected_candidate_id, score from 0-100, rationale, concerns, and metadata_status (approved, pending, or rejected).",
            "Use an empty selected_candidate_id and rejected status if none is sufficiently specific.",
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
    concerns = _string_tuple(result.get("concerns", []))
    try:
        score = max(0, min(100, int(result.get("score", 70))))
    except (TypeError, ValueError):
        score = 70
    status = str(result.get("metadata_status", "")).strip().lower()
    if status not in {"approved", "pending", "rejected"}:
        status = "approved" if score >= 80 else "pending"
    if selected and selected not in valid_ids:
        selected = ""
        status = "rejected"
        concerns = concerns + ("No valid candidate was selected.",)
    elif not selected:
        status = "rejected"
    if score < 70 and status == "approved":
        status = "pending"
    return AlignmentReview(
        selected_candidate_id=selected,
        score=score,
        rationale=str(result.get("rationale", "Best metadata match among the available candidates.")).strip(),
        concerns=concerns,
        metadata_status=status,
    )
