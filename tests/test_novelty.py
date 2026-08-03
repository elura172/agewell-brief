import json
from types import SimpleNamespace

from agewell.agents import novelty_editor
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
