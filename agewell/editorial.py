from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from openai import OpenAI

from agewell.agents import chat_completion_with_fallback, llm_thinking_kwargs


def _string_tuple(value: Any) -> tuple[str, ...]:
    """Normalize model output without accidentally splitting strings into characters."""
    if isinstance(value, str):
        cleaned = value.strip()
        return (cleaned,) if cleaned else ()
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


GLOBAL_FORBIDDEN_IMAGE_TERMS: tuple[str, ...] = (
    "cosmetic", "skincare", "skin care", "serum", "dropper", "lotion", "makeup",
    "lipstick", "mascara", "nail polish", "perfume", "fragrance", "beauty product",
    "beenaturalles", "spa treatment", "facial mask", "manicure", "pedicure",
    "leather jacket", "fashion model", "glamour", "runway", "lingerie", "bikini",
    "swimsuit", "boudoir", "posing in", "crypto", "bitcoin", "stock market",
    "wedding", "bride", "groom", "nightclub", "cocktail party",
)

CATEGORY_VISUAL_DISCIPLINE: dict[str, dict[str, tuple[str, ...]]] = {
    "brain health": {
        "visual_anchors": (
            "neuroscience laboratory, brain MRI or fMRI scan display, optical microscope, "
            "electrophysiology researcher, or quiet focused reading/study in natural light"
        ),
        "positive_tokens": (
            "brain", "neuroscience", "microscope", "laboratory", "research", "science",
            "scientist", "medical", "scan", "imaging", "neuron", "cognitive", "study",
            "reading", "chess", "library", "clinic", "sleep",
        ),
        "forbidden_tokens": (
            "driving", "car interior", "highway", "traffic", "automobile", "steering wheel",
            "wooden balcony", "barefoot woman stands", "skateboard", "surfing", "double exposure",
        ),
        "fallback_queries": (
            "neuroscience researcher brain scan",
            "scientist microscope laboratory research",
            "medical imaging monitor laboratory",
        ),
    },
    "sleep health": {
        "visual_anchors": (
            "calm dim bedroom at dusk or night, soft bedside lamp, linen bedding, "
            "sleep laboratory polysomnography, or quiet morning window light"
        ),
        "positive_tokens": (
            "sleep", "bedroom", "bed", "pillow", "linen", "night", "dusk", "dawn",
            "morning light", "rest", "slumber", "circadian", "lamp", "window", "laboratory",
        ),
        "forbidden_tokens": (
            "wooden balcony", "forest", "hiking", "gym", "office meeting", "driving",
            "car", "highway", "party", "concert",
        ),
        "fallback_queries": (
            "quiet bedroom linen morning light",
            "sleeping adult dark bedroom pillow",
            "sleep research laboratory monitor",
        ),
    },
    "metabolic health": {
        "visual_anchors": (
            "whole culinary ingredients (olive oil, leafy greens, legumes, berries), "
            "kitchen food preparation, metabolic/biochemistry research laboratory, or glucose monitoring"
        ),
        "positive_tokens": (
            "olive", "vegetables", "food", "cooking", "kitchen", "meal", "nutrition",
            "diet", "fresh", "herbs", "tomatoes", "fish", "berries", "coffee", "tea",
            "glucose", "laboratory", "microscope", "scientist", "cell", "metabolism",
        ),
        "forbidden_tokens": (
            "brown bottle", "dropper", "essential oil", "cosmetic", "skincare", "lotion",
            "perfume", "candle", "candy", "soda",
        ),
        "fallback_queries": (
            "olive oil fresh vegetables kitchen",
            "biochemistry scientist microscope laboratory",
            "whole food ingredients wooden table",
        ),
    },
    "gut health": {
        "visual_anchors": (
            "fermented foods, fiber-rich vegetables, botanical herbs, petri dish microbiology, "
            "or microscope laboratory research"
        ),
        "positive_tokens": (
            "vegetables", "fermented", "food", "microbiology", "petri", "microscope",
            "laboratory", "scientist", "fiber", "greens", "herbs", "kitchen", "organic",
            "probiotic", "gut", "culture",
        ),
        "forbidden_tokens": (
            "brown bottle", "dropper", "cosmetic", "makeup", "car", "highway",
        ),
        "fallback_queries": (
            "microbiology petri dish laboratory",
            "fresh vegetables herbs wooden board",
            "scientist microscope cell culture",
        ),
    },
    "cellular senescence": {
        "visual_anchors": (
            "fluorescence or optical microscopy, cell culture laboratory, pipette and petri dishes, "
            "or botanical polyphenol sources"
        ),
        "positive_tokens": (
            "cell", "microscope", "laboratory", "scientist", "research", "pipette",
            "biology", "tissue", "petri", "dna", "molecular", "science",
        ),
        "forbidden_tokens": (
            "brown bottle", "dropper", "cosmetic", "skincare", "balcony", "car interior",
        ),
        "fallback_queries": (
            "cell biology scientist microscope",
            "laboratory pipette cell culture",
            "molecular biology research laboratory",
        ),
    },
    "longevity": {
        "visual_anchors": (
            "cellular biology laboratory, microscopy, or active older adults walking, swimming, "
            "cycling, or gardening outdoors in natural light"
        ),
        "positive_tokens": (
            "older", "senior", "walking", "hiking", "running", "stairs", "outdoor",
            "garden", "laboratory", "microscope", "scientist", "research", "nature",
            "exercise", "trail", "swimming", "cycling",
        ),
        "forbidden_tokens": (
            "brown bottle", "dropper", "cosmetic", "skincare", "hospital bed", "wheelchair",
        ),
        "fallback_queries": (
            "older adult walking nature trail",
            "cellular aging researcher microscope",
            "active senior outdoor morning light",
        ),
    },
    "mobility": {
        "visual_anchors": (
            "older adults walking outdoors, climbing stairs, strength training, balance practice, "
            "or physical therapy biomechanics"
        ),
        "positive_tokens": (
            "walking", "running", "stairs", "steps", "exercise", "strength", "stretching",
            "mobility", "trail", "outdoor", "shoes", "athletic", "physiotherapy", "balance",
            "park", "path",
        ),
        "forbidden_tokens": (
            "car interior", "driving", "cosmetic", "bedroom",
        ),
        "fallback_queries": (
            "older adult walking stone path",
            "senior strength training exercise",
            "person climbing outdoor steps",
        ),
    },
    "detoxification": {
        "visual_anchors": (
            "clean flowing water, analytical chemistry laboratory, glass beaker filtration, "
            "or mineral-rich natural springs and botanicals"
        ),
        "positive_tokens": (
            "water", "glass", "laboratory", "chemistry", "filtration", "scientist",
            "beaker", "mineral", "stream", "clear", "analysis", "microscope",
        ),
        "forbidden_tokens": (
            "cosmetic", "serum", "makeup", "perfume", "car", "traffic",
        ),
        "fallback_queries": (
            "clear water glass natural light",
            "analytical chemistry laboratory scientist",
            "water quality testing laboratory",
        ),
    },
    "consumer safety": {
        "visual_anchors": (
            "analytical quality-control laboratory, pharmacist inspecting medication labels, "
            "or chromatography testing equipment"
        ),
        "positive_tokens": (
            "pharmacist", "laboratory", "testing", "quality", "scientist", "medicine",
            "label", "inspection", "pharmacy", "research", "capsule", "analysis",
        ),
        "forbidden_tokens": (
            "fashion", "glamour", "balcony", "beach",
        ),
        "fallback_queries": (
            "pharmacist checking medicine label",
            "quality control laboratory scientist",
            "pharmaceutical testing laboratory equipment",
        ),
    },
    "men's health": {
        "visual_anchors": (
            "older man exercising outdoors, strength training, clinical consultation, "
            "or biomedical research laboratory"
        ),
        "positive_tokens": (
            "man", "male", "exercise", "running", "walking", "strength", "doctor",
            "clinic", "laboratory", "scientist", "outdoor", "fitness",
        ),
        "forbidden_tokens": (
            "cosmetic", "makeup", "perfume", "nightclub",
        ),
        "fallback_queries": (
            "older man walking outdoor trail",
            "mature man strength training",
            "medical researcher laboratory microscope",
        ),
    },
    "general wellness": {
        "visual_anchors": (
            "credible biomedical research laboratory, outdoor daylight movement, "
            "or whole-food kitchen preparation"
        ),
        "positive_tokens": (
            "research", "laboratory", "scientist", "walking", "nature", "morning",
            "light", "water", "tea", "food", "garden", "microscope", "outdoor",
        ),
        "forbidden_tokens": (
            "cosmetic", "serum", "dropper", "leather jacket", "car interior",
        ),
        "fallback_queries": (
            "biomedical researcher microscope laboratory",
            "older adult walking morning light",
            "whole food preparation natural light",
        ),
    },
}


def _fallback_image_queries(source_title: str, category: str) -> tuple[str, str, str]:
    title = source_title.lower()
    if any(term in title for term in ("mediterranean", "olive oil", "polyphenol")):
        return (
            "Mediterranean food preparation",
            "olive oil fresh vegetables mediterranean",
            "biochemistry scientist microscope laboratory",
        )
    if any(term in title for term in ("diet", "food", "nutrition", "protein", "fasting", "eating", "meal")):
        return (
            "fresh vegetables whole food kitchen",
            "healthy meal ingredients wooden table",
            "nutrition researcher laboratory microscope",
        )
    if any(term in title for term in ("sleep", "circadian", "insomnia", "slow-wave", "delta", "dream", "nap", "melatonin")):
        return (
            "quiet bedroom linen morning light",
            "calm bedroom night bedside lamp",
            "neuroscience researcher brain scan",
        )
    if any(term in title for term in ("supplement", "hidden drug", "product notification", "fraud", "recall", "fda")):
        return (
            "pharmacist checking medicine label",
            "quality control laboratory scientist",
            "pharmaceutical testing laboratory equipment",
        )
    if any(term in title for term in ("speech", "language", "voice", "hearing", "auditory")):
        return (
            "neuroscience researcher computer monitor",
            "brain imaging laboratory scientist",
            "clinical researcher audio waveforms",
        )
    if any(term in title for term in ("microbiome", "gut", "bacteria", "intestinal", "probiotic", "ferment")):
        return (
            "microbiology petri dish laboratory",
            "fresh vegetables fiber ingredients kitchen",
            "scientist microscope cell culture",
        )
    if any(term in title for term in ("mitochond", "senescen", "autophagy", "telomere", "stem cell", "microprotein")):
        return (
            "cell biology scientist microscope",
            "laboratory pipette cell culture",
            "molecular biology research laboratory",
        )
    if any(term in title for term in ("walk", "stair", "step", "gait", "ankle", "muscle", "strength", "exercise")):
        return (
            "older adult walking stone path",
            "person climbing outdoor steps",
            "senior strength training exercise",
        )
    discipline = CATEGORY_VISUAL_DISCIPLINE.get(category.lower(), CATEGORY_VISUAL_DISCIPLINE["general wellness"])
    queries = discipline["fallback_queries"]
    return (queries[0], queries[1], queries[2])


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
    response = chat_completion_with_fallback(
        client,
        model,
        temperature=0.15,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": f"{system_prompt}\nReturn exactly one valid JSON object and no surrounding text."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    raw_text = (response.choices[0].message.content or "{}").strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
        raw_text = re.sub(r"\n?```$", "", raw_text).strip()
    value = json.loads(raw_text or "{}")
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


# Same category vocabulary as pipeline.classify()'s keyword rules, plus the
# "general wellness" fallback. Kept as a separate constant rather than importing
# from pipeline.py to avoid a circular import (pipeline.py already imports from
# this module).
CATEGORIES = (
    "consumer safety", "men's health", "metabolic health", "detoxification",
    "gut health", "cellular senescence", "mobility", "brain health",
    "sleep health", "longevity", "general wellness",
)


def verify_category(
    client: OpenAI,
    model: str,
    title: str,
    summary: str,
    proposed_category: str,
) -> dict[str, Any]:
    """Sanity-check classify()'s keyword-matched category against the actual
    content, and flag content that doesn't belong on the site at all.

    classify() is first-match-wins keyword matching over the raw title+summary,
    which reliably breaks on multi-topic abstracts and incidental word overlap
    — observed 2026-08-10: a memory-recall study filed as "consumer safety"
    because its abstract contains the word "recall", and a general aging
    proteomics paper filed as "gut health" because "microbiome" appeared as a
    secondary detail. This is a second, independent pass reading the actual
    subject rather than pattern-matching words.

    Also flags on_mission=False for content classify() will happily tag with
    *some* category but that isn't actually about human aging/longevity/
    functional health — basic-biology tooling papers (a crustacean neuropeptide
    database) or off-species research (an insect biofilm-sniffing biosensor)
    that a keyword filter can't distinguish from genuinely relevant coverage.
    """
    payload = {
        "title": title,
        "summary": summary[:1500],
        "proposed_category": proposed_category,
        "valid_categories": list(CATEGORIES),
    }
    result = _json_agent(
        client,
        model,
        (
            "You are Agewell Brief's category verifier. The site covers human aging, longevity, "
            "and functional health — biophysics, cellular senescence, metabolic health, brain health, "
            "sleep, gut health, mobility, and consumer safety as they relate to healthy aging. "
            "A proposed_category was assigned by keyword matching and may be wrong: multi-topic "
            "abstracts and incidental word overlap (e.g. 'recall' in a memory study, not a product "
            "recall) commonly produce mismatches. Read the actual subject and pick the single best-fit "
            "category from valid_categories, or confirm the proposed one if it's already correct. "
            "Separately, set on_mission=false only for content that isn't really about human aging/"
            "longevity/health at all — basic-biology tooling papers, databases, or research in other "
            "species with no stated human-health relevance. Being a preprint or narrow-topic study is "
            "not by itself a reason to flag off-mission; being off-subject is."
        ),
        payload,
        250,
    )
    category = str(result.get("category", "")).strip().lower()
    if category not in CATEGORIES:
        category = proposed_category
    return {
        "category": category,
        "on_mission": bool(result.get("on_mission", True)),
        "reason": str(result.get("reason", ""))[:300],
    }


def caption_image(
    client: OpenAI,
    model: str,
    image_alt: str,
    headline: str,
    dek: str,
) -> str:
    """Write a one-sentence caption connecting the actual selected photo to
    the actual article, instead of the generic placeholder every brief with
    an image previously shipped ("A glimpse of the everyday routines behind
    this story.") regardless of what the photo showed or what the piece was
    about — flagged 2026-08-10 by request, with the example of a strawberry
    close-up on a piece about sugar signaling.

    Grounded in image_alt (the provider's own description of the photo, real
    and specific — not invented) so the caption can't drift into describing a
    scene that isn't actually in the image.
    """
    payload = {
        "image_description": image_alt,
        "headline": headline,
        "dek": dek,
        "output": {"caption": "one sentence, specific to both the image and the article's actual point"},
    }
    result = _json_agent(
        client,
        model,
        (
            "You write photo captions for Agewell Brief. Given the real description of the selected "
            "photo and the article it illustrates, write one sentence that connects what's actually in "
            "the frame to the article's specific point — not a generic mood line. "
            "Example: a close-up of a strawberry, on a piece distinguishing natural fruit sugar from "
            "processed sweetness, becomes something like 'A strawberry's sweetness is the real signal "
            "this piece is about — not the metabolic switch that processed sugar flips.' "
            "Stay factual to image_description; do not describe anything not stated in it. "
            "No em dash required, but keep it to one sentence, plain language, no hedging."
        ),
        payload,
        150,
    )
    caption = str(result.get("caption", "")).strip()
    return caption or "A glimpse of the everyday routines behind this story."


def _sanitize_search_queries(
    raw_queries: tuple[str, ...],
    source_title: str,
    category: str,
) -> tuple[str, str, str]:
    """Enforce concrete 3-5 word Unsplash/Pexels queries and blend with category-disciplined fallbacks."""
    fallbacks = list(_fallback_image_queries(source_title, category))
    generic_or_trap_markers = (
        "healthy daily life",
        "health research natural light",
        "active adult everyday life",
        "adult daily life",
        "information highway",
        "lonely brain",
        "liquid chromatography",
        "brown bottle",
        "dropper bottle",
        "cosmetic",
        "skincare",
    )
    discipline = CATEGORY_VISUAL_DISCIPLINE.get(category.lower(), CATEGORY_VISUAL_DISCIPLINE["general wellness"])
    forbidden = GLOBAL_FORBIDDEN_IMAGE_TERMS + discipline.get("forbidden_tokens", ())

    cleaned: list[str] = []
    for query in raw_queries:
        q = re.sub(r"[^a-zA-Z0-9\s-]", " ", query).strip()
        words = [w for w in q.split() if len(w) >= 2]
        if not (2 <= len(words) <= 6):
            continue
        q_lower = " ".join(words).lower()
        if any(marker in q_lower for marker in generic_or_trap_markers):
            continue
        if any(term in q_lower for term in forbidden):
            continue
        normalized = " ".join(words[:5])
        if normalized.lower() not in {c.lower() for c in cleaned}:
            cleaned.append(normalized)

    # Always ensure the 3-query portfolio includes at least one deterministic
    # category/topic anchor query so overly narrow LLM phrasing never leaves
    # the candidate pool empty or drifted.
    if len(cleaned) >= 2:
        cleaned = cleaned[:2]
    for fb in fallbacks:
        if fb.lower() not in {c.lower() for c in cleaned}:
            cleaned.append(fb)
        if len(cleaned) >= 3:
            break
    while len(cleaned) < 3:
        cleaned.append(fallbacks[len(cleaned) % len(fallbacks)])
    return (cleaned[0], cleaned[1], cleaned[2])


def candidate_passes_discipline(
    candidate: dict[str, Any],
    category: str,
    source_title: str = "",
    headline: str = "",
    image_brief: ImageBrief | None = None,
) -> tuple[bool, int, str]:
    """Evaluate a candidate's metadata against category and thematic discipline.

    Returns (passed, thematic_score, reason).
    """
    discipline = CATEGORY_VISUAL_DISCIPLINE.get(category.lower(), CATEGORY_VISUAL_DISCIPLINE["general wellness"])
    alt = str(candidate.get("alt", "")).lower()
    tags_raw = candidate.get("tags", ())
    tags = " ".join(str(t).lower() for t in tags_raw) if isinstance(tags_raw, (list, tuple)) else str(tags_raw).lower()
    creator = str(candidate.get("creator", "")).lower()
    creator_url = str(candidate.get("creator_url", "")).lower()
    metadata = f"{alt} {tags} {creator} {creator_url}"

    for term in GLOBAL_FORBIDDEN_IMAGE_TERMS:
        if term in metadata:
            return False, 0, f"Rejected global off-theme stock term: '{term}'"

    title_lower = f"{source_title} {headline}".lower()
    for term in discipline.get("forbidden_tokens", ()):
        # Only enforce a category forbidden token if the story itself isn't explicitly about that term
        if term in metadata and term not in title_lower:
            return False, 0, f"Rejected category-forbidden visual trap for {category}: '{term}'"

    # Specific check against cosmetic/dropper bottles posing as lab science
    if ("brown bottle" in metadata or "dropper" in metadata or "amber bottle" in metadata) and not any(
        lab_term in metadata for lab_term in ("microscope", "hospital", "pharmacy", "vaccine", "clinic")
    ):
        return False, 0, "Rejected amber/brown dropper bottle (cosmetic/essential-oil stock trap)"

    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into", "over", "under",
        "study", "studies", "research", "scientists", "reveals", "linked", "shows",
        "could", "might", "after", "before", "their", "about", "years", "older",
        "aging", "ageing", "health", "human", "people", "adults", "first", "found",
        "new", "hidden", "broken", "signals", "lonely", "waves", "early", "warning",
        "more", "less", "than", "what", "when", "where", "which", "while", "between",
    }
    def _stem(word: str) -> str:
        base = re.sub(r"(?:ing|ers|er|ed|es|s)$", "", word)
        return base if len(base) >= 3 else word.rstrip("s")

    positive_tokens = {_stem(t) for t in discipline.get("positive_tokens", ()) if " " not in t}
    story_tokens = {
        _stem(token)
        for token in re.findall(r"[a-z]{3,}", f"{source_title} {headline}".lower())
        if token not in stopwords and len(_stem(token)) >= 3
    }
    query_tokens: set[str] = set()
    if image_brief:
        for q in image_brief.search_queries + (image_brief.subject, image_brief.setting):
            query_tokens.update(
                _stem(t) for t in re.findall(r"[a-z]{3,}", q.lower()) if t not in stopwords
            )

    metadata_words = {
        _stem(w) for w in re.findall(r"[a-z]{3,}", f"{alt} {tags}") if w not in stopwords
    }
    cat_hits = len(positive_tokens & metadata_words) + sum(
        1 for phrase in discipline.get("positive_tokens", ()) if " " in phrase and phrase in f"{alt} {tags}"
    )
    story_hits = len(story_tokens & metadata_words)
    query_hits = len(query_tokens & metadata_words)

    if cat_hits == 0 and story_hits == 0 and query_hits == 0:
        return False, 15, f"Candidate metadata ('{alt[:60]}') has zero overlap with category '{category}' or story subject"

    score = min(98, 55 + cat_hits * 10 + story_hits * 12 + query_hits * 8)
    return True, score, f"Matched {cat_hits} category tokens, {story_hits} story tokens, {query_hits} query tokens"


def deterministic_select_image(
    candidates: list[dict[str, Any]],
    category: str,
    source_title: str,
    headline: str,
    image_brief: ImageBrief,
) -> AlignmentReview:
    """Select the highest-scoring candidate that passes category and thematic discipline."""
    best_id = ""
    best_score = 0
    best_reason = "No candidate passed category and thematic discipline."
    rejected_reasons: list[str] = []

    for candidate in candidates:
        cid = str(candidate.get("candidate_id", ""))
        passed, score, reason = candidate_passes_discipline(
            candidate, category, source_title, headline, image_brief
        )
        if not passed:
            rejected_reasons.append(f"{cid}: {reason}")
            continue
        if score > best_score:
            best_score = score
            best_id = cid
            best_reason = reason

    if not best_id:
        return AlignmentReview(
            selected_candidate_id="",
            score=0,
            rationale="All candidates failed category and thematic discipline.",
            concerns=tuple(rejected_reasons[:4]) or ("No candidate matched category visual anchors.",),
            metadata_status="rejected",
        )

    return AlignmentReview(
        selected_candidate_id=best_id,
        score=best_score,
        rationale=f"Selected via category & thematic discipline ({category}): {best_reason}.",
        concerns=(),
        metadata_status="approved" if best_score >= 75 else "pending",
    )


def direct_image(
    client: OpenAI,
    model: str,
    source_title: str,
    category: str,
    story: dict[str, Any],
) -> ImageBrief:
    discipline = CATEGORY_VISUAL_DISCIPLINE.get(category.lower(), CATEGORY_VISUAL_DISCIPLINE["general wellness"])
    payload = {
        "source_title": source_title,
        "category": category,
        "category_visual_anchors": discipline["visual_anchors"],
        "category_forbidden_traps": discipline["forbidden_tokens"],
        "story": story,
        "output": {
            "editorial_intent": "one sentence",
            "subject": "specific visible subject",
            "setting": "specific visible setting",
            "mood": "three concise adjectives",
            "composition": "landscape editorial composition",
            "avoid": "array of visual exclusions",
            "search_queries": "array of exactly three concrete stock-photo queries (3-5 words each)",
        },
        "requirements": [
            "Direct an editorial photograph aligned with both the story's concrete subject and its category_visual_anchors.",
            "NEVER literalize headline metaphors: e.g., 'information highway' must never query roads, cars, or driving; 'lonely brain waves' must never query beaches, oceans, or people standing on balconies; 'biological clock' must never query alarm clocks.",
            "Avoid cosmetic/skincare bottles, amber dropper vials, fashion portraits, leather jackets, and unrelated vacation/balcony scenes.",
            "Return exactly three concrete Unsplash/Pexels search queries, each 3-5 simple visual words (nouns and setting).",
            "Do not use multi-word academic compound jargon (like 'liquid chromatography vial' or 'transcriptomic senescence assay') which causes stock photo APIs to return cosmetic dropper bottles.",
            "Query 1 must depict the tangible physical subject of the story (e.g., 'olive oil fresh vegetables mediterranean', 'quiet bedroom linen morning light', 'older adult climbing stone steps').",
            "Query 2 must depict the scientific or anatomical research context from category_visual_anchors (e.g., 'neuroscience researcher brain scan', 'cell biology scientist microscope').",
            "Query 3 must provide a clean secondary visual angle anchored in the category.",
        ],
    }
    result = _json_agent(
        client,
        model,
        "You are the visual director for Agewell Brief, an authoritative longevity and biophysics publication. Enforce strict category and thematic discipline.",
        payload,
        1000,
    )
    raw_queries = _string_tuple(result.get("search_queries", []))
    queries = _sanitize_search_queries(raw_queries, source_title, category)
    avoid = _string_tuple(result.get("avoid", []))
    return ImageBrief(
        editorial_intent=str(result.get("editorial_intent", "Show the story's human relevance without overclaiming.")).strip(),
        subject=str(result.get("subject", "an authentic person or research setting")).strip(),
        setting=str(result.get("setting", "a credible everyday environment")).strip(),
        mood=str(result.get("mood", "alert, capable, and natural")).strip(),
        composition=str(result.get("composition", "landscape editorial framing with a clear focal subject")).strip(),
        avoid=avoid or ("fearful expressions", "cosmetic dropper bottles", "literalized metaphors", "patronizing retirement stereotypes"),
        search_queries=queries,
    )


def review_image_metadata(
    client: OpenAI,
    model: str,
    story: dict[str, Any],
    image_brief: ImageBrief,
    candidates: list[dict[str, Any]],
    category: str = "general wellness",
    source_title: str = "",
) -> AlignmentReview:
    if not candidates:
        raise ValueError("No image candidates were supplied")

    headline = str(story.get("headline", ""))
    # Pre-filter candidates through deterministic category & thematic discipline
    compliant_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        passed, _, _ = candidate_passes_discipline(
            candidate, category, source_title, headline, image_brief
        )
        if passed:
            compliant_candidates.append(candidate)

    discipline = CATEGORY_VISUAL_DISCIPLINE.get(category.lower(), CATEGORY_VISUAL_DISCIPLINE["general wellness"])
    payload = {
        "category": category,
        "category_visual_anchors": discipline["visual_anchors"],
        "source_title": source_title,
        "story": story,
        "image_brief": image_brief.to_dict(),
        "candidates": compliant_candidates or candidates,
        "requirements": [
            "Select the single candidate whose alt text and tags most accurately match BOTH the story's specific topic and the category_visual_anchors.",
            "Do not claim to have seen pixels.",
            "Reject any candidate that represents a literalized metaphor (e.g. cars/driving for brain 'highways', ocean/balcony scenes for 'waves'), cosmetics/skincare dropper bottles, or generic fashion portraits.",
            "Reject generic lifestyle imagery when it does not depict the actual subject or scientific domain of the story.",
            "Return selected_candidate_id, score from 0-100, rationale, concerns, and metadata_status (approved, pending, or rejected).",
            "Use an empty selected_candidate_id and rejected status if none is sufficiently specific.",
        ],
    }
    result = _json_agent(
        client,
        model,
        "You are Agewell Brief's image-to-story metadata proofreader. Enforce strict category and thematic alignment.",
        payload,
        1000,
    )
    valid_by_id = {str(candidate["candidate_id"]): candidate for candidate in compliant_candidates}
    selected = str(result.get("selected_candidate_id", ""))
    concerns = _string_tuple(result.get("concerns", []))
    try:
        score = max(0, min(100, int(result.get("score", 70))))
    except (TypeError, ValueError):
        score = 70
    status = str(result.get("metadata_status", "")).strip().lower()
    if status not in {"approved", "pending", "rejected"}:
        status = "approved" if score >= 80 else "pending"
    if selected and selected not in valid_by_id:
        selected = ""
        status = "rejected"
        concerns = concerns + ("Selected candidate was not in the discipline-compliant pool.",)
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
