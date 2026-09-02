from scripts.social_manifest import update_platform_state


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
