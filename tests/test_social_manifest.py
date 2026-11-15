from scripts.social_manifest import update_platform_state
from scripts.social_package import clean_markdown, package


def test_repeated_status_error_does_not_rewrite_timestamp():
    state = {
        "status": "queued",
        "last_error": "HTTPError",
        "updated_at": "2026-08-22T02:42:04+00:00",
    }

    assert update_platform_state(state, {"last_error": "HTTPError"}) is False
    assert state["updated_at"] == "2026-08-22T02:42:04+00:00"


def test_changed_status_clears_old_error_and_updates_state():
    state = {
        "status": "queued",
        "last_error": "HTTPError",
        "updated_at": "2026-08-22T02:42:04+00:00",
    }

    changed = update_platform_state(
        state,
        {"status": "completed", "success": True, "post_id": "post-1", "url": "https://example.test/post"},
        clear=("last_error",),
    )

    assert changed is True
    assert state["status"] == "completed"
    assert "last_error" not in state
    assert state["updated_at"] != "2026-08-22T02:42:04+00:00"


def test_social_package_strips_headings_cleanly_and_uses_broadsheet_palette(tmp_path):
    post = tmp_path / "2026-11-15-acarbose.md"
    post.write_text(
        '---\n'
        'title: "Acarbose Preserves Spatial Memory in Aging Mice"\n'
        'description: "Glucose control protects normal brain aging but cannot clear amyloid plaques."\n'
        'draft: false\n'
        'category: "brain health"\n'
        'source_url: "https://example.test/paper"\n'
        '---\n\n'
        'Glucose control protects normal brain aging but cannot clear amyloid plaques.\n\n'
        '## The geroscience divergence\n\n'
        'Researchers tested middle-aged wild-type and transgenic mice across water mazes.\n\n'
        '> **Evidence note:** Conducted in mice only.\n',
        encoding="utf-8",
    )

    cleaned = clean_markdown(post.read_text(encoding="utf-8"))
    assert "The geroscience divergence" not in cleaned
    assert "Evidence note" not in cleaned

    pkg = package(post)
    assert pkg is not None
    mpt = pkg["mpt_job"]
    assert mpt["text_fore_color"] == "#FAF6EE"
    assert mpt["highlight_color"] != "#00F0FF"
    assert mpt["subtitle_glow_enabled"] is False
    assert "The g." not in mpt["script"]
    assert "longevity becomes effortless" not in mpt["script"]
    assert "✨" not in pkg["facebook"]["title"]
