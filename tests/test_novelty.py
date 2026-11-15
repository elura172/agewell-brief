import json
from types import SimpleNamespace

from agewell.agents import _deterministic_novelty, article_id, assignment_editor, novelty_editor
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
