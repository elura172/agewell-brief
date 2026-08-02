from agewell.pipeline import FeedItem, classify, slug


def test_classify_mobility():
    item = FeedItem("Walking and balance", "A new study", "https://example.test/1", "")
    assert classify(item) == "mobility"


def test_slug_is_stable():
    assert slug("A Bright, New Finding!") == "a-bright-new-finding"
