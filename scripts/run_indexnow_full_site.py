import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content/posts"
KEY_FILE = ROOT / "public/c82fc24c87f9437da381a53fd326273d.txt"
SITE_URL = "https://agewellbrief.com"

def get_all_public_urls() -> list[str]:
    urls = [
        f"{SITE_URL}/",
        f"{SITE_URL}/about/",
        f"{SITE_URL}/frontier-map/",
        f"{SITE_URL}/mind-ocean/",
        f"{SITE_URL}/spiral-of-cellular-light/",
        f"{SITE_URL}/editorial-policy/",
        f"{SITE_URL}/affiliate-disclosure/",
    ]

    posts = list(POSTS_DIR.glob("*.md"))
    for p in posts:
        content = p.read_text(encoding="utf-8")
        if "draft: true" in content:
            continue
        slug = p.stem
        urls.append(f"{SITE_URL}/brief/{slug}/")

    return urls

def main():
    if not KEY_FILE.exists():
        print(f"❌ Key file missing at {KEY_FILE}")
        return

    key = KEY_FILE.read_text(encoding="utf-8").strip()
    urls = get_all_public_urls()

    print(f"📡 Submitting {len(urls)} public URLs to IndexNow (Bing & Seznam Search Engine Indexing)...\n")

    from scripts.submit_indexnow import submit
    exit_code = submit(urls)

    if exit_code == 0:
        print("\n✨ Instant IndexNow Submission Complete! Bing & Seznam will crawl and index the site immediately.")
    else:
        print("\n⚠️ IndexNow submission returned a non-zero exit code.")

if __name__ == "__main__":
    main()
