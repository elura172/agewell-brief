#!/usr/bin/env python
"""Replace every legacy resource card in published briefs with Spiral cards.

Third-party affiliate offers are retired. Each brief gets the one spiral matching
the mechanism its story is about: an opening card after the first section, a mid
card in longer pieces, and a closing card before the source note.

Idempotent — existing spiral cards are stripped and rebuilt, so it is safe to
re-run after editing config/spiral-programs.json.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agewell.pipeline import FeedItem, program_resources, spiral_card, spiral_for  # noqa: E402

CARD_RE = re.compile(r"\n*<aside class=\"resource-card.*?</aside>", re.S)
FIELD_RE = "^-*{key}: \"(.*)\"$"


def field(text: str, key: str) -> str:
    match = re.search(FIELD_RE.format(key=key), text, re.M)
    return match.group(1) if match else ""


def rewire(path: Path, resources: dict) -> str | None:
    text = path.read_text(encoding="utf-8")
    head, sep, body = text.partition("\n---\n")
    if not sep:
        return None

    category = field(text, "category")
    item = FeedItem(
        title=field(text, "title"),
        summary=" ".join(CARD_RE.sub("", body).split()[:120]),
        link=field(text, "source_url"),
        published="",
    )
    spiral = spiral_for(category, item, resources)
    if not spiral:
        return None

    body = CARD_RE.sub("", body)
    sections = [m.start() for m in re.finditer(r"^## ", body, re.M)]

    # Closing card goes above the source note so the article ends on the program.
    # The trailing "\n" is required, not cosmetic: spiral_card ends on "</aside>"
    # and source_at points at the newline before "### Source", so without it the
    # heading lands on the line straight after the closing tag. Markdown keeps an
    # HTML block open until a blank line, so the heading gets swallowed into the
    # block and renders as literal "### Source" text.
    source_at = body.find("\n### Source")
    closing = spiral_card(spiral, category, placement="closing")
    body = body[:source_at] + "\n" + closing + "\n" + body[source_at:] if source_at != -1 else body + closing

    # Opening card after the first section, mirroring the pipeline's placement.
    if len(sections) >= 2:
        cut = sections[1]
        body = body[:cut] + spiral_card(spiral, category, placement="opening").lstrip("\n") + "\n\n" + body[cut:]

    path.write_text(head + sep + body, encoding="utf-8")
    return spiral["name"]


def main() -> int:
    resources = program_resources()
    if not resources.get("spirals"):
        print("No spirals configured", file=sys.stderr)
        return 1

    counts: dict[str, int] = {}
    skipped = 0
    for path in sorted((ROOT / "content/posts").glob("*.md")):
        name = rewire(path, resources)
        if name is None:
            skipped += 1
        else:
            counts[name] = counts.get(name, 0) + 1

    for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3}  {name}")
    print(f"rewired {sum(counts.values())} briefs, skipped {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
