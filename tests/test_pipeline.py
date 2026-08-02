import json
from types import SimpleNamespace

import pytest

from agewell import pipeline
from agewell.pipeline import (
    FeedItem,
    FeedSource,
    choose_edition,
    classify,
    draft,
    extract_article_text,
    fetch_ranked_items,
    feed_sources,
    normalized_title,
    relevance_score,
    select_ranked_items,
    select_offer,
    slug,
    tracked_offer_url,
)


def test_classify_mobility():
    item = FeedItem("Walking and balance", "A new study", "https://example.test/1", "")
    assert classify(item) == "mobility"


def test_classify_alzheimers_as_brain_health():
    item = FeedItem("A new Alzheimer's blood test", "Researchers report early findings", "https://example.test/brain", "")
    assert classify(item) == "brain health"


def test_slug_is_stable():
    assert slug("A Bright, New Finding!") == "a-bright-new-finding"


def test_tracking_id_is_added_to_encrypted_hoplink():
    result = tracked_offer_url(
        "https://abc123.hop.clickbank.net/?campaign=morning",
        "metabolic health",
        "8a2f9b1c",
    )
    assert result == (
        "https://abc123.hop.clickbank.net/"
        "?campaign=morning&tid=agewell_metabolic_health_8a2f9b1c"
    )


def test_existing_tracking_id_is_replaced():
    result = tracked_offer_url(
        "https://abc123.hop.clickbank.net/?tid=old_value",
        "mobility",
        "deadbeef",
    )
    assert result == "https://abc123.hop.clickbank.net/?tid=agewell_mobility_deadbeef"


def test_non_clickbank_offer_is_rejected():
    with pytest.raises(ValueError):
        tracked_offer_url("https://example.com/offer", "mobility", "deadbeef")


def test_general_wellness_offer_does_not_cross_categories():
    configured = {"general wellness": "https://fallback.hop.clickbank.net"}
    assert select_offer(configured, "brain health") is None


def test_general_wellness_offer_matches_general_wellness():
    configured = {"general wellness": "https://wellness.hop.clickbank.net"}
    assert select_offer(configured, "general wellness") == configured["general wellness"]


def test_specific_offer_matches_its_category():
    configured = {
        "general wellness": "https://fallback.hop.clickbank.net",
        "mobility": "https://mobility.hop.clickbank.net",
    }
    assert select_offer(configured, "mobility") == configured["mobility"]


def test_multiple_feed_configuration(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "RSS_FEEDS_JSON",
        '[{"name":"Lively source","url":"https://example.test/feed.xml","priority":3,"headline_mode":"preserve"}]',
    )
    sources = feed_sources()
    assert sources == [FeedSource("Lively source", "https://example.test/feed.xml", 3, "preserve")]


def test_legacy_single_feed_configuration(monkeypatch):
    monkeypatch.setattr(pipeline, "RSS_FEEDS_JSON", "")
    monkeypatch.setattr(pipeline, "RSS_FEED_URL", "https://example.test/feed.xml")
    monkeypatch.setattr(pipeline, "FEED_CONFIG_FILE", pipeline.ROOT / "missing-feed-config.json")
    assert feed_sources() == [FeedSource("Primary feed", "https://example.test/feed.xml")]


def test_agewell_relevance_prioritizes_older_adult_story():
    relevant = FeedItem(
        "Walking and sleep support healthy aging",
        "A study of older adults",
        "https://example.test/relevant",
        "",
    )
    generic = FeedItem(
        "Hospital names a new director",
        "Leadership announcement",
        "https://example.test/generic",
        "",
    )
    assert relevance_score(relevant) > relevance_score(generic)


def test_normalized_title_deduplicates_punctuation():
    assert normalized_title("Sleep After 60: What Changed?") == normalized_title("Sleep after 60 — what changed")


def test_ranked_batch_limits_a_single_publisher(monkeypatch):
    monkeypatch.setattr(pipeline, "MAX_ITEMS", 3)
    monkeypatch.setattr(pipeline, "MAX_ITEMS_PER_PUBLISHER", 1)
    candidates = [
        FeedItem("Aging and sleep breakthrough", "Older adults", "https://x.test/1", "", "X Sleep", 9, "preserve", "X"),
        FeedItem("Aging and memory breakthrough", "Older adults", "https://x.test/2", "", "X Brain", 8, "preserve", "X"),
        FeedItem("Walking after 60", "Mobility", "https://fda.test/1", "", "FDA", 5, "rewrite", "FDA"),
        FeedItem("Nutrition for longevity", "Healthspan", "https://med.test/1", "", "MedlinePlus", 4, "preserve", "MedlinePlus"),
    ]

    selected = select_ranked_items(candidates)

    assert selected[0].source_group == "X"
    assert {item.source_group for item in selected} == {"X", "FDA", "MedlinePlus"}


def test_draft_disables_thinking_and_retries_invalid_json():
    class FakeCompletions:
        def __init__(self):
            self.calls: list[dict] = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            content = '{"headline":"cut off' if len(self.calls) == 1 else json.dumps(
                {
                    "headline": "A useful finding",
                    "dek": "Researchers shared a practical update.",
                    "bullets": ["First point", "Second point", "Third point"],
                    "caveat": "The evidence is still developing.",
                }
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    item = FeedItem("Source title", "Source summary", "https://example.test/story", "")

    result = draft(client, item, "general wellness")

    assert result["headline"] == "A useful finding"
    assert len(completions.calls) == 2
    assert completions.calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}


def test_extract_article_text_ignores_page_chrome():
    document = """
    <html><body><nav>This navigation should never become source material.</nav>
    <article><h2>Why the finding matters</h2>
    <p>Researchers followed older adults over several years and documented a meaningful change in mobility.</p>
    <p>The article explains the study design, its limitations, and the questions that remain unanswered.</p>
    </article><footer>This footer should also disappear entirely.</footer></body></html>
    """

    extracted = extract_article_text(document)

    assert "Researchers followed older adults" in extracted
    assert "navigation" not in extracted
    assert "footer" not in extracted


def test_fetch_ranked_items_excludes_processed_before_limiting(monkeypatch):
    items = [
        FeedItem("Aging story one", "Older adults", "https://example.test/1", ""),
        FeedItem("Aging story two", "Older adults", "https://example.test/2", ""),
        FeedItem("Aging story three", "Older adults", "https://example.test/3", ""),
    ]
    monkeypatch.setattr(pipeline, "MAX_ITEMS", 2)
    monkeypatch.setattr(pipeline, "fetch_items", lambda _source: items)

    selected = fetch_ranked_items(
        [FeedSource("Test", "https://example.test/feed")],
        {pipeline.item_id(items[0])},
    )

    assert [item.link for item in selected] == ["https://example.test/2", "https://example.test/3"]


def test_lead_draft_requests_long_structured_analysis():
    paragraph = " ".join(["Evidence from the source helps readers understand this finding without overstating what researchers know."] * 9)
    sections = [
        {"heading": heading, "paragraphs": [paragraph, paragraph]}
        for heading in ("Why it matters", "What researchers found", "How to read it", "What to do next")
    ]
    payload = {
        "headline": "A deeper look at healthy aging",
        "dek": "A useful development deserves context.",
        "sections": sections,
        "bullets": ["First point", "Second point", "Third point"],
        "caveat": "The evidence is still developing.",
    }

    class FakeCompletions:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])

    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    item = FeedItem("Source title", "Source summary", "https://example.test/story", "")

    result = draft(client, item, "longevity", "lead", paragraph)

    assert len(result["sections"]) == 4
    assert completions.kwargs["max_tokens"] == 3200


def test_choose_edition_promotes_source_rich_story(monkeypatch):
    candidates = [
        FeedItem("Top summary-only story", "Short summary", "https://example.test/1", ""),
        FeedItem("Source-rich story", "Summary", "https://example.test/2", ""),
        FeedItem("Third story", "Summary", "https://example.test/3", ""),
    ]
    monkeypatch.setattr(pipeline, "MAX_ITEMS", 3)
    monkeypatch.setattr(
        pipeline,
        "fetch_article_text",
        lambda item: "rich source material " * 200 if item.link.endswith("/2") else item.summary,
    )

    edition = choose_edition(candidates)

    assert edition[0][0].link == "https://example.test/2"
    assert edition[0][1] == "lead"
    assert [entry[1] for entry in edition[1:]] == ["signal", "signal"]
