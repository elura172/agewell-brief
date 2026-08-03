"""Regenerate only previously published articles with thin source extraction.

This is intentionally separate from the daily edition runner. It reads the
edition source audit, fetches each linked source page again, and rewrites only
the article body while preserving frontmatter, canonical slug, images, and
existing resource cards.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

from openai import OpenAI

from agewell.pipeline import (
    FeedItem,
    build_evidence_packet,
    draft,
    fetch_article_text,
)


ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content/posts"
EDITION_DIR = ROOT / ".state/editions"
BACKFILL_DIR = ROOT / ".state/backfill"
SOURCE_LIMIT = 18_000


def frontmatter_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*[\"']?(.*?)[\"']?\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def split_document(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("article is missing YAML frontmatter")
    marker = text.find("\n---", 4)
    if marker == -1:
        raise ValueError("article frontmatter is not closed")
    return text[: marker + 4], text[marker + 4 :].lstrip()


def article_id_from_post(path: Path) -> str:
    return path.stem.rsplit("-", 1)[-1]


def audited_targets(min_source_chars: int, limit: int) -> list[tuple[Path, dict[str, object]]]:
    rows: dict[str, dict[str, object]] = {}
    for source_file in sorted(EDITION_DIR.glob("**/sources.json")):
        try:
            payload = json.loads(source_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, list):
            continue
        for row in payload:
            if not isinstance(row, dict):
                continue
            article_id = str(row.get("article_id", ""))
            if not article_id or int(row.get("source_characters", 0) or 0) >= min_source_chars:
                continue
            rows[article_id] = row

    targets: list[tuple[Path, dict[str, object]]] = []
    for article_id, row in rows.items():
        matches = sorted(POSTS_DIR.glob(f"*-{article_id[:8]}.md"))
        if not matches:
            continue
        path = matches[0]
        if frontmatter_value(path.read_text(encoding="utf-8"), "draft").lower() == "true":
            continue
        targets.append((path, row))
    return targets[:limit]


def existing_cards(body: str) -> list[str]:
    return re.findall(r"<aside\b.*?</aside>", body, flags=re.DOTALL | re.IGNORECASE)


def source_block(body: str) -> str:
    marker = "### Source"
    if marker in body:
        block = body[body.index(marker) :].strip()
        return re.sub(r"\n?>\s*\*\*Health note:\*\*.*$", "", block, flags=re.DOTALL).strip()
    return "### Source\n"


def render_body(content: dict[str, object], old_body: str, content_type: str) -> str:
    lines = [str(content.get("dek", "")).strip()]
    sections = content.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            heading = str(section.get("heading", "")).strip()
            paragraphs = section.get("paragraphs")
            if heading and isinstance(paragraphs, list):
                lines.extend([f"## {heading}", "", "\n\n".join(str(p).strip() for p in paragraphs if str(p).strip())])

    bullets = content.get("bullets")
    if not isinstance(bullets, list):
        bullets = []
    lines.extend(["## Three things to remember", "", "\n".join(f"- {str(bullet).strip()}" for bullet in bullets if str(bullet).strip())])

    cards = existing_cards(old_body)
    if cards:
        lines.append("\n\n".join(cards))
    lines.append(source_block(old_body))
    health_note = str(content.get("caveat", "This article is informational and is not medical advice.")).strip()
    lines.append(f"> **Health note:** {health_note}")
    return "\n\n".join(line for line in lines if line.strip()).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=26)
    parser.add_argument("--min-source-chars", type=int, default=2500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required")

    model = os.environ.get("LLM_MODEL", "deepseek-v4-flash")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    client = OpenAI(api_key=api_key, base_url=base_url)
    targets = audited_targets(args.min_source_chars, args.limit)
    if not targets:
        print("No thin published articles matched the backfill threshold.")
        return 0

    audit: list[dict[str, object]] = []
    failures = 0
    for path, row in targets:
        old_text = path.read_text(encoding="utf-8")
        frontmatter, old_body = split_document(old_text)
        title = frontmatter_value(old_text, "title") or str(row.get("title", path.stem))
        summary = old_body.split("\n\n", 1)[0].strip()
        link = frontmatter_value(old_text, "source_url") or str(row.get("url", ""))
        source_name = frontmatter_value(old_text, "source_name") or str(row.get("source_name", "Unknown source"))
        category = frontmatter_value(old_text, "category") or str(row.get("category", "general wellness"))
        content_type = frontmatter_value(old_text, "content_type") or str(row.get("content_type", "signal"))
        item = FeedItem(title, summary, link, frontmatter_value(old_text, "date"), source_name)
        before = len(summary)
        try:
            source_text = fetch_article_text(item)
            evidence = build_evidence_packet(client, model, title, summary, source_text, link)
            content = draft(client, item, category, content_type, source_text, evidence, [])
            after = len(source_text)
            if not args.dry_run:
                path.write_text(frontmatter + "\n" + render_body(content, old_body, content_type), encoding="utf-8")
            audit.append({
                "article": path.name,
                "source_url": link,
                "source_name": source_name,
                "content_type": content_type,
                "source_characters_before": int(row.get("source_characters", before) or before),
                "source_characters_after": after,
                "status": "dry_run" if args.dry_run else "updated",
            })
            print(f"{ 'DRY ' if args.dry_run else '' }updated {path.name}: {after} source characters")
        except Exception as exc:
            failures += 1
            audit.append({"article": path.name, "source_url": link, "status": "failed", "error": str(exc)})
            print(f"failed {path.name}: {exc}", file=sys.stderr)

    BACKFILL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (BACKFILL_DIR / f"{stamp}.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"Backfill complete: {len(audit) - failures} updated, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
