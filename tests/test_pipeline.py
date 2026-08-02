import pytest

from agewell.pipeline import FeedItem, classify, select_offer, slug, tracked_offer_url


def test_classify_mobility():
    item = FeedItem("Walking and balance", "A new study", "https://example.test/1", "")
    assert classify(item) == "mobility"


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


def test_general_wellness_offer_is_the_fallback():
    configured = {"general wellness": "https://fallback.hop.clickbank.net"}
    assert select_offer(configured, "brain health") == configured["general wellness"]


def test_specific_offer_wins_over_fallback():
    configured = {
        "general wellness": "https://fallback.hop.clickbank.net",
        "mobility": "https://mobility.hop.clickbank.net",
    }
    assert select_offer(configured, "mobility") == configured["mobility"]
