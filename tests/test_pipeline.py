import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agewell import pipeline
from agewell.affiliates import parse_offer_config
from agewell.pipeline import (
    DraftGenerationError,
    FeedItem,
    FeedSource,
    choose_edition,
    classify,
    draft,
    extract_article_text,
    fetch_ranked_items,
    feed_sources,
    normalized_title,
    markdown,
    normalize_source_url,
    parse_model_json,
    relevance_score,
    sanitize_feed_xml,
    select_ranked_items,
    select_offer,
    slug,
    tracked_offer_url,
)
from agewell.edition import audit_release
from agewell.editorial import (
    DeferredVisionReviewer,
    EvidencePacket,
    ImageBrief,
    build_evidence_packet,
    direct_image,
    review_image_metadata,
)
from agewell.images import (
    ImageCandidate,
    ImageSearchCache,
    PublishedImage,
    search_image_candidates,
    search_pexels,
    search_pixabay,
)


def test_classify_mobility():
    item = FeedItem("Walking and balance", "A new study", "https://example.test/1", "")
    assert classify(item) == "mobility"


def test_classify_alzheimers_as_brain_health():
    item = FeedItem("A new Alzheimer's blood test", "Researchers report early findings", "https://example.test/brain", "")
    assert classify(item) == "brain health"


def test_classify_sleep_story_as_sleep_health():
    item = FeedItem(
        "A new approach to insomnia",
        "Researchers studied sleep and night waking in older adults.",
        "https://example.test/sleep",
        "",
    )
    assert classify(item) == "sleep health"


def test_alzheimers_sleep_story_stays_brain_health():
    item = FeedItem(
        "Sleep disruption in Alzheimer's disease",
        "A mouse study examined amyloid and sleep.",
        "https://example.test/alzheimers-sleep",
        "",
    )
    assert classify(item) == "brain health"


def test_fat_imbalance_does_not_trigger_mobility_category():
    item = FeedItem(
        "How obesity may fuel Alzheimer's disease",
        "Researchers studied a lipid imbalance in the brain.",
        "https://example.test/metabolic",
        "",
    )
    assert classify(item) == "metabolic health"


def test_classify_tainted_supplement_alert_as_consumer_safety():
    item = FeedItem("Tainted supplement product notification", "Hidden drug warning", "https://example.test/safety", "")
    assert classify(item) == "consumer safety"


def test_classify_prostate_story_as_mens_health():
    item = FeedItem(
        "A new prostate health study",
        "Researchers followed older men.",
        "https://example.test/mens-health",
        "",
    )
    assert classify(item) == "men's health"


def test_fda_legacy_links_are_upgraded_to_https():
    assert normalize_source_url("http://www.fda.gov/drugs/example") == "https://www.fda.gov/drugs/example"
    assert normalize_source_url("http://example.test/story") == "http://example.test/story"


def test_feed_sanitizer_converts_html_entities_without_breaking_xml_entities():
    payload = (
        b"<rss><channel><item><title>Healthy aging &ndash; mobility &amp; strength</title>"
        b"<description>Unknown &madeup; entity</description></item></channel></rss>"
    )

    root = pipeline.ET.fromstring(sanitize_feed_xml(payload))
    item = root.find(".//item")

    assert item is not None
    assert item.findtext("title") == "Healthy aging \u2013 mobility & strength"
    assert item.findtext("description") == "Unknown &madeup; entity"


def test_slug_is_stable():
    assert slug("A Bright, New Finding!") == "a-bright-new-finding"


def test_pexels_search_uses_authorization(monkeypatch):
    captured = {}
    payload = {
        "photos": [
            {
                "id": 10,
                "url": "https://www.pexels.com/photo/first-10/",
                "photographer": "First Photographer",
                "photographer_url": "https://www.pexels.com/@first",
                "avg_color": "#112233",
                "alt": "First image",
                "src": {"landscape": "https://images.pexels.com/photos/10/first.jpeg"},
            },
            {
                "id": 20,
                "url": "https://www.pexels.com/photo/second-20/",
                "photographer": "Second Photographer",
                "photographer_url": "https://www.pexels.com/@second",
                "avg_color": "#445566",
                "alt": "Second image",
                "src": {"landscape": "https://images.pexels.com/photos/20/second.jpeg"},
            },
        ]
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(payload).encode()

    def fake_urlopen(request, timeout):
        captured["authorization"] = request.get_header("Authorization")
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("agewell.images.urllib.request.urlopen", fake_urlopen)
    result = search_pexels("test-key", "older couple sleeping")

    assert [candidate.provider_id for candidate in result] == ["10", "20"]
    assert captured["authorization"] == "test-key"
    assert "orientation=landscape" in captured["url"]
    assert captured["timeout"] == 30


def test_pixabay_search_returns_attributed_candidate(monkeypatch):
    payload = {
        "hits": [
            {
                "id": 44,
                "pageURL": "https://pixabay.com/photos/example-44/",
                "largeImageURL": "https://cdn.pixabay.com/photo/44.jpg",
                "user": "River Light",
                "user_id": 9,
                "tags": "walking, park, sunlight",
                "imageWidth": 1800,
                "imageHeight": 1200,
            }
        ]
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr("agewell.images.urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse())
    result = search_pixabay("test-key", "walking in a park")

    assert result[0].candidate_id == "Pixabay:44"
    assert result[0].creator == "River Light"
    assert result[0].source_url.startswith("https://pixabay.com/")


def test_image_broker_searches_both_providers_and_filters_ledger(monkeypatch, tmp_path: Path):
    brief = ImageBrief(
        "Show movement",
        "adult walker",
        "park",
        "capable",
        "landscape",
        ("fear",),
        ("adult walking park",),
    )
    pexels = ImageCandidate("Pexels", "1", "https://images.pexels.com/1", "https://www.pexels.com/1", "A", "", "Walk", (), 1200, 800)
    pixabay = ImageCandidate("Pixabay", "2", "https://cdn.pixabay.com/2", "https://pixabay.com/2", "B", "", "Walk", (), 1600, 900)
    monkeypatch.setattr("agewell.images.search_pexels", lambda *_args: [pexels])
    monkeypatch.setattr("agewell.images.search_pixabay", lambda *_args: [pixabay])

    result = search_image_candidates(
        brief,
        "pexels-key",
        "pixabay-key",
        ImageSearchCache(tmp_path / "cache.json"),
        {"Pexels:1"},
    )

    assert [candidate.candidate_id for candidate in result] == ["Pixabay:2"]


def test_image_broker_searches_all_queries_and_avoids_used_creator(monkeypatch, tmp_path: Path):
    brief = ImageBrief(
        "Show speech research",
        "speech neuroscience researcher",
        "laboratory",
        "focused",
        "landscape",
        ("generic kitchens",),
        ("speech neuroscience laboratory", "brain scan researcher", "speech therapy technology"),
    )
    calls = []

    def fake_pexels(_key, query):
        calls.append(("Pexels", query))
        creator = "https://www.pexels.com/@used" if query == brief.search_queries[0] else "https://www.pexels.com/@fresh"
        return [
            ImageCandidate(
                "Pexels",
                query.replace(" ", "-"),
                "https://images.pexels.com/example",
                "https://www.pexels.com/example",
                "Photographer",
                creator,
                query,
                (),
                1800,
                1200,
                search_query=query,
            )
        ]

    def fake_pixabay(_key, query):
        calls.append(("Pixabay", query))
        return []

    monkeypatch.setattr("agewell.images.search_pexels", fake_pexels)
    monkeypatch.setattr("agewell.images.search_pixabay", fake_pixabay)
    result = search_image_candidates(
        brief,
        "pexels-key",
        "pixabay-key",
        ImageSearchCache(tmp_path / "cache.json"),
        excluded_creator_urls={"https://www.pexels.com/@used"},
    )

    assert len(calls) == 6
    assert {candidate.search_query for candidate in result} == set(brief.search_queries[1:])


def test_metadata_review_normalizes_string_concerns_and_can_reject_all_candidates():
    class FakeCompletions:
        def create(self, **_kwargs):
            payload = {
                "selected_candidate_id": "",
                "score": 25,
                "rationale": "The kitchen scene is unrelated to speech neuroscience.",
                "concerns": "Generic lifestyle image does not show the reported subject.",
                "metadata_status": "rejected",
            }
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    brief = ImageBrief("Show research", "researcher", "lab", "focused", "landscape", (), ("speech lab",))
    candidate = ImageCandidate(
        "Pexels",
        "1",
        "https://images.pexels.com/1",
        "https://www.pexels.com/1",
        "A",
        "",
        "Woman preparing fruit in a kitchen",
        (),
        1200,
        800,
    )

    result = review_image_metadata(client, "deepseek-test", {"headline": "Speech decoded from neurons"}, brief, [candidate.to_dict()])

    assert result.metadata_status == "rejected"
    assert result.selected_candidate_id == ""
    assert result.concerns == ("Generic lifestyle image does not show the reported subject.",)


def test_image_director_uses_story_specific_fallback_queries():
    class FakeCompletions:
        def create(self, **_kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    result = direct_image(
        client,
        "deepseek-test",
        "Mediterranean diet may protect the heart",
        "brain health",
        {"headline": "Diet finding"},
    )

    assert result.search_queries[0] == "Mediterranean food preparation"
    assert all("daily life" not in query for query in result.search_queries)


def test_markdown_keeps_photo_and_attribution_metadata_together():
    item = FeedItem("Source title", "Source summary", "https://example.test/story", "", "Test Source")
    content = {
        "headline": "A useful finding",
        "dek": "A clear introduction.",
        "bullets": ["First point", "Second point", "Third point"],
        "caveat": "The study was small.",
        "sections": [],
    }
    photo = PublishedImage(
        provider="Pexels",
        provider_id="123",
        local_url="/images/editions/2026-08-02/example.webp",
        source_url="https://www.pexels.com/photo/example-123/",
        creator="A Photographer",
        creator_url="https://www.pexels.com/@photographer",
        alt="An older adult walking outdoors",
        avg_color="#aabbcc",
    )

    result = markdown(item, "mobility", content, None, photo=photo)

    assert 'image_provider: "Pexels"' in result
    assert 'image_provider_id: "123"' in result
    assert 'image: "/images/editions/2026-08-02/example.webp"' in result
    assert 'image_alt: "An older adult walking outdoors"' in result
    assert 'image_photographer: "A Photographer"' in result
    assert 'image_source_url: "https://www.pexels.com/photo/example-123/"' in result


def test_release_audit_keeps_shadow_edition_in_draft():
    story = {
        "headline": "A useful finding",
        "dek": "A clear introduction.",
        "bullets": ["One", "Two", "Three"],
    }
    result = audit_release("abc", "https://example.test/source", story, "approved", "pending")

    assert result.publishable is False
    assert "pixel-level image review is pending" in result.reasons
    assert "human editorial review is pending" in result.reasons


def test_deferred_vision_reviewer_never_claims_pixel_review():
    brief = ImageBrief("intent", "subject", "setting", "mood", "composition", (), ("query",))
    result = DeferredVisionReviewer().review("/tmp/image.webp", brief, {"headline": "Story"})

    assert result["status"] == "pending"
    assert "not configured" in result["reason"]


def test_specialist_agent_explicitly_requests_json_mode():
    class FakeCompletions:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs
            payload = {
                "study_type": "study",
                "key_claims": ["A supported claim."],
                "limitations": ["A stated limit."],
                "what_not_to_say": ["Do not overclaim."],
                "confidence": "moderate",
            }
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])

    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    result = build_evidence_packet(client, "deepseek-test", "Title", "Summary", "Source", "https://example.test")

    assert result.confidence == "moderate"
    assert "JSON" in completions.kwargs["messages"][0]["content"]


def test_run_writes_complete_shadow_edition_audit(monkeypatch, tmp_path: Path):
    item = FeedItem(
        "Walking supports healthy aging",
        "Researchers reported a practical mobility finding.",
        "https://example.test/story",
        "",
        "Test Source",
    )
    story = {
        "headline": "Walking supports healthy aging",
        "dek": "A clear introduction.",
        "bullets": ["First point", "Second point", "Third point"],
        "caveat": "The study has limits.",
        "sections": [],
    }
    evidence = EvidencePacket(
        "observational study",
        ("Walking was associated with healthier aging.",),
        ("The result does not prove causation.",),
        ("Do not promise prevention.",),
        "moderate",
    )
    brief = ImageBrief(
        "Show practical movement",
        "adult walking",
        "park",
        "capable",
        "landscape",
        ("fear",),
        ("adult walking in park",),
    )

    monkeypatch.setattr(pipeline, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path / "posts")
    monkeypatch.setattr(pipeline, "STATE_FILE", tmp_path / "processed.json")
    monkeypatch.setattr(pipeline, "PUBLIC_ROOT", tmp_path / "public")
    monkeypatch.setattr(pipeline, "EDITION_STATE_ROOT", tmp_path / "editions")
    monkeypatch.setattr(pipeline, "IMAGE_CACHE_FILE", tmp_path / "image-cache.json")
    monkeypatch.setattr(pipeline, "IMAGE_LEDGER_FILE", tmp_path / "image-ledger.json")
    monkeypatch.setattr(pipeline, "feed_sources", lambda: [FeedSource("Test", "https://example.test/feed")])
    monkeypatch.setattr(pipeline, "fetch_ranked_items", lambda *_args, **_kwargs: [item])
    monkeypatch.setattr(pipeline, "choose_edition", lambda _items: [(item, "signal", None)])
    monkeypatch.setattr(pipeline, "build_evidence_packet", lambda *_args: evidence)
    monkeypatch.setattr(pipeline, "draft", lambda *_args: story)
    monkeypatch.setattr(pipeline, "direct_image", lambda *_args: brief)
    monkeypatch.setattr(pipeline, "search_image_candidates", lambda *_args: [])

    assert pipeline.run() == 0

    edition_dates = list((tmp_path / "editions").iterdir())
    assert len(edition_dates) == 1
    edition_dirs = list(edition_dates[0].iterdir())
    assert len(edition_dirs) == 1
    expected = {
        "sources.json",
        "evidence.json",
        "drafts.json",
        "image-briefs.json",
        "candidates.json",
        "failed-drafts.json",
        "visual-reviews.json",
        "release-manifest.json",
    }
    assert {path.name for path in edition_dirs[0].iterdir()} == expected
    manifest = json.loads((edition_dirs[0] / "release-manifest.json").read_text())
    assert manifest["publishable"] is False
    assert manifest["run_id"] == edition_dirs[0].name
    assert manifest["checks"][0]["visual_review_status"] == "pending"


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


def test_unencrypted_clickbank_hoplink_keeps_affiliate_and_vendor():
    result = tracked_offer_url(
        "https://hop.clickbank.net/?affiliate=agewell&vendor=seller",
        "brain health",
        "feed1234",
    )
    assert result == (
        "https://hop.clickbank.net/"
        "?affiliate=agewell&vendor=seller&tid=agewell_brain_health_feed1234"
    )


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


def test_rich_offer_config_requires_explicit_approval():
    configured = {
        "offers": [
            {
                "category": "brain health",
                "name": "Unreviewed",
                "url": "https://unreviewed.hop.clickbank.net",
                "approved": False,
            },
            {
                "category": "brain health",
                "name": "Reviewed",
                "url": "https://reviewed.hop.clickbank.net",
                "approved": True,
            },
        ]
    }
    assert select_offer(configured, "brain health", "article-1") == "https://reviewed.hop.clickbank.net"


def test_hoplink_error_health_hides_offer():
    configured = {"brain health": "https://reviewed.hop.clickbank.net"}
    offer = parse_offer_config(configured)[0]
    assert select_offer(configured, "brain health", "article-1", {offer.offer_id: "hoplink_error"}) is None


def test_equal_priority_offers_rotate_deterministically_by_article():
    configured = {
        "sleep health": [
            "https://sleepone.hop.clickbank.net",
            "https://sleeptwo.hop.clickbank.net",
            "https://sleepthree.hop.clickbank.net",
        ]
    }
    selections = {
        select_offer(configured, "sleep health", f"article-{number}")
        for number in range(24)
    }
    assert len(selections) == 3
    assert select_offer(configured, "sleep health", "article-7") == select_offer(
        configured,
        "sleep health",
        "article-7",
    )


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
    prompt = json.loads(completions.calls[-1]["messages"][1]["content"])
    requirements = " ".join(prompt["requirements"])
    assert "clear, spirited, respectful, and concrete" in requirements
    assert "not a rigid template" in requirements
    assert "Do not invent facts" in requirements


def test_draft_retries_transient_api_failure():
    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("temporary upstream failure")
            payload = {
                "headline": "A useful finding",
                "dek": "Researchers shared a practical update.",
                "bullets": ["First point", "Second point", "Third point"],
                "caveat": "The evidence is still developing.",
            }
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])

    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    item = FeedItem("Source title", "Source summary", "https://example.test/story", "")

    result = draft(client, item, "general wellness")

    assert completions.calls == 2
    assert result["headline"] == "A useful finding"


def test_model_json_parser_recovers_redundant_closing_brace():
    assert parse_model_json('{"headline":"Useful"}\n}') == {"headline": "Useful"}


def test_model_json_parser_rejects_explanatory_trailing_text():
    with pytest.raises(json.JSONDecodeError):
        parse_model_json('{"headline":"Useful"}\nHere is another version')


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


def test_lead_retry_uses_validation_feedback_and_retains_focused_draft():
    paragraph = " ".join(["Source-grounded context helps readers understand the finding and its limits clearly."] * 5)
    payload = {
        "headline": "A focused look at healthy aging",
        "dek": "A useful development deserves context.",
        "sections": [
            {"heading": heading, "paragraphs": [paragraph, paragraph]}
            for heading in ("Why it matters", "What researchers found", "How to read it", "What to do next")
        ],
        "bullets": ["First point", "Second point", "Third point"],
        "caveat": "The evidence is still developing.",
    }

    class FakeCompletions:
        def __init__(self):
            self.calls: list[dict] = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])

    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    item = FeedItem("Source title", "Source summary", "https://example.test/story", "")

    result = draft(client, item, "longevity", "lead", "deep source material " * 300)

    assert len(completions.calls) == 2
    repair = json.loads(completions.calls[1]["messages"][-1]["content"])
    assert "too short" in repair["validation_error"]
    assert "at least 500 words" in " ".join(repair["requirements"])
    assert result["generation_status"] == "accepted_focused_fallback"
    assert "retained as a focused draft" in result["generation_note"]


def test_run_isolates_failed_story_and_keeps_the_edition(monkeypatch, tmp_path: Path):
    lead = FeedItem("Lead story", "Lead summary", "https://example.test/lead", "", "Lead Source")
    broken = FeedItem("Broken signal", "Signal summary", "https://example.test/broken", "", "Signal Source")
    story = {
        "headline": "A useful lead",
        "dek": "A clear introduction.",
        "bullets": ["First point", "Second point", "Third point"],
        "caveat": "The study has limits.",
        "sections": [],
    }
    evidence = EvidencePacket("report", ("Claim",), ("Limit",), ("No overclaim",), "moderate")
    brief = ImageBrief("Intent", "adult", "setting", "capable", "landscape", (), ("adult outdoors",))

    monkeypatch.setattr(pipeline, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path / "posts")
    monkeypatch.setattr(pipeline, "STATE_FILE", tmp_path / "processed.json")
    monkeypatch.setattr(pipeline, "PUBLIC_ROOT", tmp_path / "public")
    monkeypatch.setattr(pipeline, "EDITION_STATE_ROOT", tmp_path / "editions")
    monkeypatch.setattr(pipeline, "IMAGE_CACHE_FILE", tmp_path / "image-cache.json")
    monkeypatch.setattr(pipeline, "IMAGE_LEDGER_FILE", tmp_path / "image-ledger.json")
    monkeypatch.setattr(pipeline, "feed_sources", lambda: [FeedSource("Test", "https://example.test/feed")])
    monkeypatch.setattr(pipeline, "fetch_ranked_items", lambda *_args, **_kwargs: [lead, broken])
    monkeypatch.setattr(
        pipeline,
        "choose_edition",
        lambda _items: [(lead, "lead", "source"), (broken, "signal", None)],
    )
    monkeypatch.setattr(pipeline, "build_evidence_packet", lambda *_args: evidence)

    def fake_draft(_client, item, *_args):
        if item is broken:
            raise DraftGenerationError([{"attempt": 1, "error": "invalid JSON", "raw_response": "{"}])
        return story

    monkeypatch.setattr(pipeline, "draft", fake_draft)
    monkeypatch.setattr(pipeline, "direct_image", lambda *_args: brief)
    monkeypatch.setattr(pipeline, "search_image_candidates", lambda *_args: [])

    assert pipeline.run() == 0
    assert len(list((tmp_path / "posts").glob("*.md"))) == 1
    assert json.loads((tmp_path / "processed.json").read_text()) == [pipeline.item_id(lead)]

    run_dir = next(next((tmp_path / "editions").iterdir()).iterdir())
    failures = json.loads((run_dir / "failed-drafts.json").read_text())
    manifest = json.loads((run_dir / "release-manifest.json").read_text())
    assert failures[0]["article_id"] == pipeline.item_id(broken)
    assert failures[0]["resolution"] == "skipped"
    assert failures[0]["attempts"][0]["raw_response"] == "{"
    assert manifest["attempted_stories"] == 2
    assert manifest["generated_stories"] == 1
    assert manifest["failed_stories"] == 1


def test_failed_lead_is_downgraded_to_signal(monkeypatch, tmp_path: Path):
    item = FeedItem("Lead story", "Lead summary", "https://example.test/lead", "", "Lead Source")
    signal = {
        "headline": "A useful signal",
        "dek": "A concise introduction.",
        "bullets": ["First point", "Second point", "Third point"],
        "caveat": "The report has limits.",
        "sections": [],
    }
    evidence = EvidencePacket("report", ("Claim",), ("Limit",), ("No overclaim",), "moderate")
    brief = ImageBrief("Intent", "adult", "setting", "capable", "landscape", (), ("adult outdoors",))

    monkeypatch.setattr(pipeline, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path / "posts")
    monkeypatch.setattr(pipeline, "STATE_FILE", tmp_path / "processed.json")
    monkeypatch.setattr(pipeline, "PUBLIC_ROOT", tmp_path / "public")
    monkeypatch.setattr(pipeline, "EDITION_STATE_ROOT", tmp_path / "editions")
    monkeypatch.setattr(pipeline, "IMAGE_CACHE_FILE", tmp_path / "image-cache.json")
    monkeypatch.setattr(pipeline, "IMAGE_LEDGER_FILE", tmp_path / "image-ledger.json")
    monkeypatch.setattr(pipeline, "feed_sources", lambda: [FeedSource("Test", "https://example.test/feed")])
    monkeypatch.setattr(pipeline, "fetch_ranked_items", lambda *_args, **_kwargs: [item])
    monkeypatch.setattr(pipeline, "choose_edition", lambda _items: [(item, "lead", "source")])
    monkeypatch.setattr(pipeline, "build_evidence_packet", lambda *_args: evidence)

    def fake_draft(_client, _item, _category, content_type, *_args):
        if content_type == "lead":
            raise DraftGenerationError([{"attempt": 2, "error": "too short", "raw_response": "{}"}])
        return signal

    monkeypatch.setattr(pipeline, "draft", fake_draft)
    monkeypatch.setattr(pipeline, "direct_image", lambda *_args: brief)
    monkeypatch.setattr(pipeline, "search_image_candidates", lambda *_args: [])

    assert pipeline.run() == 0
    generated = next((tmp_path / "posts").glob("*.md")).read_text()
    assert 'content_type: "signal"' in generated
    run_dir = next(next((tmp_path / "editions").iterdir()).iterdir())
    failures = json.loads((run_dir / "failed-drafts.json").read_text())
    assert failures[0]["resolution"] == "downgraded_to_signal"


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
