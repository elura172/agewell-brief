"""Resolve ClickBank destinations and classify them for contextual placement."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = ROOT / "config/affiliate-candidates.json"
OUTPUT = ROOT / "config/affiliate-offer-review.json"
CATEGORIES = ("mobility", "sleep health", "brain health", "longevity", "metabolic health", "virility", "general wellness")


def fetch(url: str) -> dict[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "AgewellBrief affiliate review/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            html = response.read(400_000).decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.get_text(" ", strip=True) if soup.title else ""
            og = soup.find("meta", attrs={"property": "og:title"})
            h1 = soup.find("h1")
            text = " ".join(soup.get_text(" ", strip=True).split())[:5000]
            return {
                "status": str(getattr(response, "status", 200)),
                "final_url": response.geturl(),
                "title": title[:300],
                "og_title": (og.get("content", "") if og else "")[:300],
                "h1": (h1.get_text(" ", strip=True) if h1 else "")[:300],
                "text": text,
            }
    except Exception as exc:
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def classify(client: OpenAI, model: str, records: list[dict[str, str]]) -> list[dict[str, object]]:
    prompt = f"""Classify these affiliate landing pages for contextual editorial placement.
Allowed categories: {', '.join(CATEGORIES)}.
Use general wellness when the page is inaccessible, generic, or ambiguous.
Do not infer medical efficacy. Return ONLY a JSON array with one object per input:
{{"url":"...","category":"...","confidence":0.0,"name":"short neutral product name","reason":"metadata evidence only"}}

INPUT:
{json.dumps(records, ensure_ascii=False)}"""
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a cautious affiliate taxonomy editor."},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or "[]"
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    result = json.loads(content)
    if not isinstance(result, list):
        raise ValueError("DeepSeek returned a non-list classification")
    return result


def main() -> int:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("DEEPSEEK_API_KEY is required", file=sys.stderr)
        return 2
    urls = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    records = [{"url": url, **fetch(url)} for url in urls]
    client = OpenAI(api_key=api_key, base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"))
    raw = classify(client, os.getenv("LLM_MODEL", "deepseek-v4-flash"), records)
    by_url = {str(row.get("url")): row for row in raw if isinstance(row, dict)}
    offers = []
    for record in records:
        row = by_url.get(record["url"], {})
        category = str(row.get("category", "general wellness")).lower()
        confidence = float(row.get("confidence", 0))
        if category not in CATEGORIES or confidence < 0.75:
            category = "general wellness"
        offers.append({
            "category": category,
            "name": str(row.get("name") or "ClickBank offer")[:100],
            "url": record["url"],
            "approved": True,
            "priority": 30 if category != "general wellness" else 10,
            "classification_confidence": confidence,
            "classification_reason": str(row.get("reason") or "Unclassified landing page")[:240],
        })
    OUTPUT.write_text(json.dumps({"offers": offers}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(offers)} reviewed affiliate mappings to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
