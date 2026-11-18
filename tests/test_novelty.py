import json
from types import SimpleNamespace

from agewell.agents import (
    _deterministic_novelty,
    article_id,
    assignment_editor,
    novelty_editor,
    off_mission_reason,
    release_manager,
)
from agewell.pipeline import FeedItem


def test_novelty_editor_holds_generic_sleep_duration_story():
    class Completions:
        def create(self, **kwargs):
            payload = json.loads(kwargs["messages"][1]["content"])
            scores = []
            for candidate in payload["candidates"]:
                score = 22 if "6.4 to 7.8" in candidate["title"] else 86
                scores.append({
                    "article_id": candidate["article_id"],
                    "score": score,
                    "decision": "commission" if score >= 58 else "hold",
                    "novelty_type": "contextual_update",
                    "reason": "test",
                    "angle": "test angle",
                })
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"scores": scores})))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    result = novelty_editor(
        client,
        "test-model",
        [
            FeedItem("Sleeping 6.4 to 7.8 hours may slow aging, per research", "A broad association", "https://example.test/sleep", ""),
            FeedItem("A new blood test maps senescent cells in living tissue", "A named biomarker and new method", "https://example.test/frontier", ""),
        ],
        [],
        [],
    )
    assert len(result["commissioned_ids"]) == 1
    assert result["scores"][result["held_back"][0]]["score"] == 22


def test_deterministic_novelty_holds_aquaculture_production():
    salmon = _deterministic_novelty(
        "Dietary Spermidine Enhances Lipid Handling in Farmed Salmon",
        "Multiomics reveals a production signature in Atlantic salmon aquaculture cohorts.",
    )
    assert salmon["decision"] == "hold"
    assert salmon["score"] <= 35


def test_assignment_editor_supplies_output_schema_and_parses_assignments():
    captured_payloads = []

    class Completions:
        def create(self, **kwargs):
            payload = json.loads(kwargs["messages"][1]["content"])
            captured_payloads.append(payload)
            first_id = payload["candidates"][0]["article_id"]
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps(
                                {
                                    "edition_angle": "Cellular metabolism and brain resilience",
                                    "assignments": [
                                        {
                                            "article_id": first_id,
                                            "role": "lead",
                                            "angle": "Report the exact study boundary.",
                                            "confidence": 0.91,
                                            "reason": "Strongest empirical trial.",
                                        }
                                    ],
                                    "held_back": [],
                                }
                            )
                        )
                    )
                ]
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    item = FeedItem("Acarbose preserves spatial memory in aging mice", "Summary", "https://example.test/acarbose", "")
    result = assignment_editor(client, "test-model", [item], [], [], 1)
    assert "output_schema" in captured_payloads[0]
    assert result["mode"] == "agent"
    assert result["assignments"][0]["article_id"] == article_id(item.link)


def test_deterministic_gate_holds_pure_pharma_epidemiology_and_anti_supplement_drafts():
    # 1. Pure pharma/vaccine epidemiology with no cellular mechanism -> held
    pharma = _deterministic_novelty(
        "Osteoporosis Drugs Linked to Lower Dementia Risk in Major Study",
        "Observational insurance records show lower rates of dementia diagnoses among patients taking bisphosphonates.",
    )
    assert pharma["decision"] == "hold"
    assert pharma["score"] <= 25

    # 2. Mechanistic cellular pathway study involving a compound -> allowed
    mech_reason = off_mission_reason(
        "Semaglutide Restores Mitochondrial Autophagy and AMPK Signaling in Aging Brain Tissue",
        "Researchers measured mitochondrial membrane potential and lysosomal mitophagy.",
    )
    assert mech_reason is None

    # 3. release_manager blocks drafts with blanket anti-supplement generalizations
    held_review = release_manager(
        "https://example.test/yale",
        {
            "headline": "Yale Study Shows Prescription Drugs Alter Epigenetic Clocks",
            "dek": "Prescription drugs alter epigenetic blood markers, while popular over-the-counter supplements miss the mark.",
            "paragraphs": ["Over-the-counter supplements generally failed to shift methylation clocks."],
            "bullets": ["b1", "b2", "b3"],
        },
        {"status": "approved", "flagged": False, "issues": []},
    )
    assert held_review["status"] == "held"
    assert any("off-mission hold" in r for r in held_review["reasons"])


def test_match_biophysics_pioneers_matches_20_founder_codex():
    from pathlib import Path
    from agewell.context import match_biophysics_pioneers

    lineage_path = Path(__file__).resolve().parent.parent / "config/biophysics-lineage.json"
    pioneers = json.loads(lineage_path.read_text(encoding="utf-8"))["pioneers"]
    assert len(pioneers) == 20
    names = {p["name"] for p in pioneers}
    assert "Dr. Mae-Wan Ho" in names
    assert "Dr. Michael Levin" in names
    assert "Dr. Maiken Nedergaard" in names
    assert "Dr. Douglas C. Wallace" in names
    assert "Dr. Martin Picard" in names

    matched = match_biophysics_pioneers(
        "Glymphatic Sleep Clearance and Astrocyte Aquaporin-4 Channels in Brain Aging",
        "Slow-wave sleep drives cerebrospinal fluid interstitial clearance of beta-amyloid and tau.",
        category="Brain & Mind",
        spiral="second-spiral",
        limit=2,
    )
    assert len(matched) == 2
    assert any("Nedergaard" in m["scientist"] for m in matched)

