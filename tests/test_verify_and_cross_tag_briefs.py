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


def test_cross_tagging_uses_word_boundaries_and_ignores_image_alt_substrings(tmp_path):
    post = tmp_path / "acarbose.md"
    post.write_text(
        '---\n'
        'title: "Acarbose Preserves Spatial Memory in Aging Mice"\n'
        'description: "An FDA-approved diabetes drug restores hippocampal synapse resilience."\n'
        'category: "brain health"\n'
        'image_alt: "a microscope resting on a black table"\n'
        '---\n\n'
        'Resting-state networks and caloric restriction restore neural resilience.\n',
        encoding="utf-8",
    )

    assert audit_file(post) is True
    tagged = post.read_text(encoding="utf-8")
    assert "'sleep health'" not in tagged
    assert "'consumer safety'" not in tagged
    assert "'brain health'" in tagged
