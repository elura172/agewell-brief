#!/usr/bin/env python3
"""Backfill Post-Constructivist / Bauhaus scientific lithograph plates across the Agewell Brief archive.

Supports both direct Gemini API image generation (once Cloud Billing Tier 1 is linked to GEMINI_API_KEY)
and `--print-prompts` for batch subagent rendering in Antigravity on Google AI Ultra.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openai import OpenAI

from agewell.editorial import ImageBrief, SPIRAL_GEOMETRIC_MOTIFS, direct_image
from agewell.images import build_lithograph_prompt, generate_lithograph_plate
from agewell.pipeline import GEMINI_API_KEY, LLM_BASE_URL, MODEL, PUBLIC_ROOT, quote


POSTS_DIR = ROOT / "content" / "posts"

FOLIO_01_SLUGS: tuple[str, ...] = (
    "2026-11-08-broken-signals-in-deep-sleep-how-lonely-brain-waves-reveal-hidden-memo-bba5979f",
    "2026-08-15-your-brain-s-plumbing-runs-on-a-24-hour-clock-new-study-links-wakefuln-af82708a",
    "2026-08-13-astrocytes-the-sleep-architects-rewiring-memory-circuits-eb053f14",
    "2026-11-10-mapping-the-neuro-metabolic-circuit-of-hypoxia-induced-longevity-f4e7b57f",
    "2026-11-10-transcriptional-reprogramming-of-immature-neurons-preserves-cognition--5d996610",
    "2026-11-10-rejuvenating-liver-microcirculation-halves-circulating-alzheimer-s-pro-6de37cde",
)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, flags=re.DOTALL)
    if not match:
        return {}, text
    raw_fm, body = match.group(1), match.group(2)
    fields: dict[str, str] = {}
    for line in raw_fm.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fields[k.strip()] = v.strip().strip('"')
    return fields, body


def update_post_image_frontmatter(
    path: Path,
    local_url: str,
    alt: str,
    caption: str,
    provider_id: str,
    width: int = 1376,
    height: int = 768,
) -> None:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Missing frontmatter in {path}")
    raw_fm, body = match.group(1), match.group(2)
    image_keys = {
        "image_id",
        "image_provider",
        "image_provider_id",
        "image",
        "image_alt",
        "image_caption",
        "image_width",
        "image_height",
        "image_photographer",
        "image_photographer_url",
        "image_source_url",
        "image_review_status",
        "image_avg_color",
    }
    kept_lines = [
        "draft: false" if line.strip() == "draft: true" else line
        for line in raw_fm.splitlines()
        if line.split(":", 1)[0].strip() not in image_keys
    ]
    kept_lines.extend(
        [
            'image_provider: "Agewell Visual Desk"',
            f'image_provider_id: "{quote(provider_id)}"',
            f'image: "{quote(local_url)}"',
            f'image_alt: "{quote(alt)}"',
            f'image_caption: "{quote(caption)}"',
            f"image_width: {width}",
            f"image_height: {height}",
            'image_photographer: "Agewell Brief Visual Desk"',
            'image_review_status: "vision-approved"',
            'image_avg_color: "#f4efe4"',
        ]
    )
    new_fm = "\n".join(kept_lines)
    path.write_text(f"---\n{new_fm}\n---\n{body}", encoding="utf-8")


def select_targets(scope: str, slug_filter: str = "", limit: int = 0) -> list[Path]:
    all_posts = sorted(POSTS_DIR.glob("*.md"), reverse=True)
    selected: list[Path] = []
    for path in all_posts:
        if slug_filter and slug_filter not in path.stem:
            continue
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm.get("image_provider") == "Agewell Visual Desk" and not slug_filter:
            continue
        if scope == "phase1":
            if not (path.stem.startswith("2026-11-") or path.stem in FOLIO_01_SLUGS):
                continue
        elif scope == "leads":
            if fm.get("content_type") != "lead":
                continue
        selected.append(path)
        if limit and len(selected) >= limit:
            break
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=("phase1", "leads", "all"),
        default="phase1",
        help="Which archive tier to backfill (default: phase1 = Folio 01 + remaining Nov 2026 briefs).",
    )
    parser.add_argument("--slug", default="", help="Filter to a specific post slug substring.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of briefs to process.")
    parser.add_argument("--use-llm-director", action="store_true", help="Call direct_image() LLM before building prompt.")
    parser.add_argument("--print-prompts", action="store_true", help="Print 80/20 Study+Spiral lithograph prompts without calling the image API.")
    args = parser.parse_args()

    targets = select_targets(args.scope, slug_filter=args.slug, limit=args.limit)
    print(f"Found {len(targets)} target brief(s) for scope={args.scope!r}")

    api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    client = OpenAI(api_key=api_key, base_url=LLM_BASE_URL) if (args.use_llm_director and api_key) else None

    generated = 0
    for path in targets:
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        headline = fm.get("title", path.stem)
        first_para = next((p.strip() for p in body.split("\n\n") if p.strip() and not p.strip().startswith("#")), "")
        dek = fm.get("description") or first_para
        category = fm.get("category", "general wellness")
        spiral_name = fm.get("spiral", "Luminous Mind")
        edition_id = fm.get("edition_id") or (path.stem[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", path.stem) else "archive")
        article_id = hashlib.sha256(path.stem.encode("utf-8")).hexdigest()[:24]

        brief: ImageBrief | None = None
        if client is not None:
            try:
                brief = direct_image(
                    client,
                    MODEL,
                    fm.get("source_title", headline),
                    category,
                    {"headline": headline, "dek": dek},
                    spiral_name=spiral_name,
                )
            except Exception as exc:
                print(f"  [director fallback] {path.stem}: {exc}", file=sys.stderr)

        prompt = build_lithograph_prompt(headline, dek, category, brief, spiral_name=spiral_name)
        if args.print_prompts:
            print(f"\n=== {path.stem} ({spiral_name} | {category}) ===")
            print(prompt)
            continue

        photo = generate_lithograph_plate(
            headline=headline,
            dek=dek,
            category=category,
            brief=brief,
            public_root=PUBLIC_ROOT,
            edition_id=edition_id,
            article_slug=path.stem,
            article_id=article_id,
            api_key=api_key,
            spiral_name=spiral_name,
        )
        if photo is None:
            print(f"  [skipped] {path.stem}: Gemini Image API returned no image (check Tier 1 Cloud Billing on GEMINI_API_KEY).", file=sys.stderr)
            continue

        update_post_image_frontmatter(
            path=path,
            local_url=photo.local_url,
            alt=photo.alt,
            caption=photo.caption or dek,
            provider_id=photo.provider_id,
            width=photo.width,
            height=photo.height,
        )
        generated += 1
        print(f"  [ok] {path.stem} -> {photo.local_url} ({photo.width}x{photo.height})")

    if not args.print_prompts:
        print(f"Completed: {generated}/{len(targets)} lithograph plate(s) generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
