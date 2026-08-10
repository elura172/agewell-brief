"""Backfill evidence_position on the existing archive.

Only content_type "signal" or "lead" briefs are classified — evergreen/editorial
framework pages aren't reporting a single study's maturity, and got a mislabel
("speculative", from build_evidence_packet returning study_type values like
"plain-language guide") when tested against them on 2026-08-09. Those keep the
existing schema default instead.

Usage:
    python3 -m scripts.classify_archive_evidence_position
    python3 -m scripts.classify_archive_evidence_position --limit 5
"""

import argparse
import os
import re
from pathlib import Path

from openai import OpenAI

from agewell.editorial import build_evidence_packet, classify_evidence_position
from agewell.pipeline import quote

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content/posts"

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")


def classify_article(filepath: Path) -> bool:
    text = filepath.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False
    frontmatter, body = parts[1], parts[2]

    if "evidence_position:" in frontmatter:
        return False

    content_type_match = re.search(r'content_type:\s*"(.*?)"', frontmatter)
    content_type = content_type_match.group(1) if content_type_match else "signal"
    if content_type not in {"signal", "lead"}:
        return False

    title_match = re.search(r'title:\s*"(.*?)"', frontmatter)
    source_url_match = re.search(r'source_url:\s*"(.*?)"', frontmatter)
    if not title_match:
        return False
    title = title_match.group(1)
    source_url = source_url_match.group(1) if source_url_match else ""

    print(f"Classifying: {filepath.name}")
    try:
        evidence = build_evidence_packet(client, "deepseek-chat", title, body[:1000], body[:4000], source_url)
        position = classify_evidence_position(client, "deepseek-chat", evidence.study_type, evidence.key_claims, evidence.limitations)
    except Exception as e:
        print(f"  ✗ failed: {e}")
        return False

    updated_fm = frontmatter.strip() + f'\nevidence_position: "{quote(position)}"\n'
    filepath.write_text(f"---{updated_fm}---{body}", encoding="utf-8")
    print(f"  ✓ {position} (study_type: {evidence.study_type})")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    all_posts = sorted(POSTS_DIR.glob("*.md"))
    pending = [p for p in all_posts if "evidence_position:" not in p.read_text(encoding="utf-8")]
    targets = pending[: args.limit] if args.limit else pending
    print(f"{len(all_posts)} briefs total, {len(pending)} not yet classified, processing {len(targets)}.\n")

    count = 0
    for p in targets:
        if classify_article(p):
            count += 1

    print(f"\nDone! Classified {count} of {len(targets)} attempted.")


if __name__ == "__main__":
    main()
