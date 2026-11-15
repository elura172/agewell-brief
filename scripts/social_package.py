"""Create channel-specific social packages for newly released briefs."""

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
    text = re.sub(r"<aside\b.*?</aside>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^\s*#{1,6}\s+.*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>.*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*-\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"!\[[^]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`>#]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def first_complete_sentences(text: str, max_chars: int = 260) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    if not sentences:
        return ""
    chosen: list[str] = []
    total = 0
    for sentence in sentences:
        projected = total + (1 if chosen else 0) + len(sentence)
        if chosen and projected > max_chars:
            break
        chosen.append(sentence)
        total = projected
        if total >= max_chars:
            break
    result = " ".join(chosen)
    if len(result) > max_chars + 40:
        clipped = result[:max_chars].rsplit(" ", 1)[0].rstrip(",;:")
        return f"{clipped}."
    return result


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


def trending_items(path: Path = Path("src/data/trending.json")) -> dict[str, dict[str, int]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(item["slug"]): {"rank": index + 1, "visits": int(item.get("visits", 0))}
        for index, item in enumerate(payload.get("articles", []))
        if item.get("slug") and int(item.get("visits", 0)) > 0
    }


def generate_broadsheet_reel_script(title: str, category: str, body: str, description: str = "") -> str:
    """Generate a calm, factual broadsheet dispatch script free of hype or truncated markdown."""
    lead_summary = first_complete_sentences(description or body, max_chars=240)
    detail_summary = first_complete_sentences(body, max_chars=300)
    narrative = detail_summary if detail_summary and detail_summary != lead_summary else lead_summary
    return (
        f"From Agewell Brief: {title}. "
        f"{narrative} "
        f"Read the full source-linked dispatch and primary study caveats at AgewellBrief.com."
    )


generate_cosmic_reel_script = generate_broadsheet_reel_script


def package(path: Path, trend: dict[str, int] | None = None) -> dict[str, object] | None:
    text = path.read_text(encoding="utf-8")
    if frontmatter_value(text, "draft").lower() == "true":
        return None
    title = frontmatter_value(text, "title") or path.stem
    description = frontmatter_value(text, "description")
    category = frontmatter_value(text, "category") or "general wellness"
    body = clean_markdown(text)
    hook = first_complete_sentences(description or body, max_chars=280)
    url = f"{BASE_URL}/brief/{path.stem}/"
    source_url = frontmatter_value(text, "source_url") or frontmatter_value(text, "original_source")
    trend_note = (
        {"rank": trend["rank"], "reader_visits": trend["visits"]}
        if trend
        else None
    )
    script = generate_broadsheet_reel_script(title, category, body, description=description)
    # Warm mineral & copperplate highlight palette aligned with Agewell Brief's broadsheet UI
    cat_lower = category.lower()
    if "gut" in cat_lower or "mobility" in cat_lower:
        highlight_color = "#6E9B77"  # Mineral Sage
    elif "brain" in cat_lower or "sleep" in cat_lower:
        highlight_color = "#C98B3B"  # Warm Ochre
    else:
        highlight_color = "#D98A2B"  # Saffron Copper

    return {
        "article": path.stem,
        "url": url,
        "category": category,
        "trend": trend_note,
        "source_url": source_url,
        "content_record": {
            "article_id": path.stem,
            "article_url": url,
            "title": title,
            "category": category,
            "source_url": source_url,
            "editorial_body": body,
        },
        "mpt_job": {
            "status": "ready_for_mpt",
            "subject": title,
            "article_url": url,
            "video_aspect": "9:16",
            "voice_name": "en-US-AvaNeural",
            "script": script,
            "source_url": source_url,
            "trend": trend_note,
            "text_fore_color": "#FAF6EE",
            "highlight_color": highlight_color,
            "stroke_color": "#181A1B",
            "stroke_width": 2,
            "font_size": 46,
            "subtitle_bottom_margin": 210,
            "max_words_per_line": 4,
            "active_word_scale": 1.06,
            "uppercase_keywords": False,
            "bold_keywords": True,
            "subtitle_bg_color": "rgba(24, 26, 27, 0.82)",
            "subtitle_bg_padding": 12,
            "subtitle_glow_enabled": False,
            "requires_video_qa": False,
        },
        "facebook": {
            "title": f"{title}\n\n{hook}",
            "link_url": url,
        },
        "tiktok": {
            "hook": title,
            "script": script,
            "caption": f"{title}. Source-linked longevity and biophysics reporting from Agewell Brief. Full study and evidentiary notes in bio. #longevityscience #biophysics #healthspan #agewellbrief",
            "link_in_bio": url,
            "media_status": "ready_for_mpt",
        },
        "youtube": {
            "title": title[:95],
            "description": f"{script}\n\nRead the full source-linked brief: {url}\n\nIndependent healthspan and biophysics reporting from Agewell Brief.",
            "media_status": "ready_for_mpt",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".state/social/latest.json")
    parser.add_argument("--trending", action="store_true", help="Also package the current reader-trending briefs")
    parser.add_argument("--max-trending", type=int, default=5)
    args = parser.parse_args()
    paths = changed_posts()
    trends = trending_items() if args.trending else {}
    for slug in list(trends)[: args.max_trending]:
        path = Path("content/posts") / f"{slug}.md"
        if path.exists():
            paths.append(path)
    paths = list(dict.fromkeys(paths))
    packages = [item for path in paths if (item := package(path, trends.get(path.stem)))]
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "release_status": "published",
        "dry_run": False,
        "schema_version": 3,
        "includes_trending": args.trending,
        "packages": packages,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Social package: prepared {len(packages)} released article(s) for social handoff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
