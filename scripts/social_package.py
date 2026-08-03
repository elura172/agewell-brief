"""Create channel-specific social packages for newly released briefs.

This phase is intentionally dry-run: it prepares copy and canonical URLs but
does not publish anything. Upload-Post can be enabled after the packages have
been reviewed and a vertical video renderer is in place for TikTok/YouTube.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path


BASE_URL = "https://agewellbrief.com"


def frontmatter_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*[\"']?(.*?)[\"']?\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def clean_markdown(text: str) -> str:
    text = re.sub(r"^---.*?---\s*", "", text, count=1, flags=re.DOTALL)
    text = re.sub(r"!\[[^]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`>#]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def changed_posts() -> list[Path]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "content/posts"],
        check=True,
        capture_output=True,
        text=True,
    )
    paths = []
    for line in result.stdout.splitlines():
        path = line[3:].strip()
        if path.startswith("content/posts/") and path.endswith(".md"):
            paths.append(Path(path))
    return list(dict.fromkeys(paths))


def package(path: Path) -> dict[str, object] | None:
    text = path.read_text(encoding="utf-8")
    if frontmatter_value(text, "draft").lower() == "true":
        return None
    title = frontmatter_value(text, "title") or path.stem
    category = frontmatter_value(text, "category") or "general wellness"
    body = clean_markdown(text)
    hook = body[:280].rstrip(".") + "."
    url = f"{BASE_URL}/brief/{path.stem}/"
    return {
        "article": path.stem,
        "url": url,
        "category": category,
        "source_url": frontmatter_value(text, "original_source"),
        "content_record": {
            "article_id": path.stem,
            "article_url": url,
            "title": title,
            "category": category,
            "source_url": frontmatter_value(text, "original_source"),
            "editorial_body": body,
        },
        "mpt_job": {
            "status": "ready_for_mpt",
            "subject": title,
            "article_url": url,
            "video_aspect": "9:16",
            "voice_name": "en-US-JennyNeural",
            "text_fore_color": "#FFFFFF",
            "stroke_color": "#000000",
            "stroke_width": 4,
            "font_size": 64,
            "requires_video_qa": True,
        },
        "facebook": {
            "title": f"{title}\n\n{hook}",
            "link_url": url,
        },
        "tiktok": {
            "hook": title,
            "script": f"{title}. Here is what the source found, what it does not prove, and why it matters.",
            "caption": f"{title} — read the full brief at Agewell Brief.",
            "link_in_bio": url,
            "media_status": "needs_vertical_video",
        },
        "youtube": {
            "title": title[:100],
            "description": f"{hook}\n\nRead the full brief: {url}\n\nSource-led health reporting from Agewell Brief.",
            "media_status": "needs_vertical_video",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".state/social/latest.json")
    args = parser.parse_args()
    packages = [item for path in changed_posts() if (item := package(path))]
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "dry_run": True,
        "schema_version": 2,
        "packages": packages,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Social package: prepared {len(packages)} released article(s); dry-run only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
