from scripts.verify_and_cross_tag_briefs import audit_file


def test_cross_tagging_keeps_canonical_frontmatter_delimiters(tmp_path):
    post = tmp_path / "brief.md"
    post.write_text(
        '---\ntitle: "A finding"\ncategory: "brain health"\n---\n\nBrain aging research.\n',
        encoding="utf-8",
    )

    assert audit_file(post) is True
    once = post.read_text(encoding="utf-8")
    assert once.startswith('---\ntitle: "A finding"')
    assert "\n---\n\nBrain aging research.\n" in once

    assert audit_file(post) is True
    assert post.read_text(encoding="utf-8") == once
