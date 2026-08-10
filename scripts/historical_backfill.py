"""Pull real historical studies from PubMed and bioRxiv/medRxiv and run them
through the same drafting pipeline as the daily edition (evidence packet,
autoresearch antecedents, evidence_position classification, spiral routing).

RSS feeds only carry recent items, so there was no existing path to genuine
historical depth. PubMed and bioRxiv both support real date-range queries —
these are real studies, not invented backstory.

Usage:
    python3 -m scripts.historical_backfill --start 2024-01-01 --end 2024-12-31 --limit 10 --dry-run
    python3 -m scripts.historical_backfill --start 2024-01-01 --end 2024-12-31 --limit 200
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from openai import OpenAI

import agewell.pipeline as pipeline
from agewell.agents import article_id, novelty_editor
from agewell.pipeline import (
    FeedItem,
    NOVELTY_MIN_SCORE,
    classify,
    item_id,
    markdown,
    program_resources,
    spiral_for,
)

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content/posts"

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")

# Same category keyword rules as classify(), used to keep bioRxiv results (which
# has no keyword search, only date-range) on-topic instead of pulling everything
# posted that day across every field of biology.
TOPIC_TERMS = [
    "aging", "ageing", "longevity", "lifespan", "healthspan", "senescence", "senolytic",
    "mitochondri", "metabolic", "glucose", "insulin", "microbiome", "gut", "sleep",
    "circadian", "cognitive", "memory", "brain", "dementia", "alzheimer", "inflammation",
    "biophoton", "exclusion zone", "EZ water", "epigenetic", "autophagy", "telomere",
]


def existing_source_urls() -> set[str]:
    urls = set()
    for p in POSTS_DIR.glob("*.md"):
        text = p.read_text(encoding="utf-8")
        m = re.search(r'source_url:\s*"(.*?)"', text)
        if m:
            urls.add(m.group(1))
    return urls


def fetch_pubmed(query: str, date_from: str, date_to: str, max_results: int) -> list[FeedItem]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    search_params = urllib.parse.urlencode({
        "db": "pubmed", "term": query, "datetype": "pdat",
        "mindate": date_from, "maxdate": date_to,
        "retmax": max_results, "retmode": "json", "sort": "relevance",
    })
    with urllib.request.urlopen(f"{base}/esearch.fcgi?{search_params}", timeout=30) as r:
        ids = json.loads(r.read())["esearchresult"].get("idlist", [])
    if not ids:
        return []
    time.sleep(0.4)

    fetch_params = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "xml"})
    with urllib.request.urlopen(f"{base}/efetch.fcgi?{fetch_params}", timeout=30) as r:
        root = ET.fromstring(r.read())

    items = []
    for article in root.findall(".//PubmedArticle"):
        title_el = article.find(".//ArticleTitle")
        abstract_el = article.find(".//AbstractText")
        pmid_el = article.find(".//PMID")
        year_el = article.find(".//PubDate/Year")
        if title_el is None or abstract_el is None or pmid_el is None:
            continue
        title = "".join(title_el.itertext()).strip()
        abstract = "".join(abstract_el.itertext()).strip()
        if not title or not abstract:
            continue
        pmid = pmid_el.text
        year = year_el.text if year_el is not None else date_from[:4]
        items.append(FeedItem(
            title=title,
            summary=abstract,
            link=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            published=year,
            source_name="PubMed",
            source_group="PubMed",
        ))
    return items


def fetch_biorxiv(server: str, date_from: str, date_to: str, max_results: int) -> list[FeedItem]:
    items: list[FeedItem] = []
    cursor = 0
    while len(items) < max_results:
        url = f"https://api.biorxiv.org/details/{server}/{date_from}/{date_to}/{cursor}"
        with urllib.request.urlopen(url, timeout=30) as r:
            payload = json.loads(r.read())
        collection = payload.get("collection", [])
        if not collection:
            break
        for paper in collection:
            title = (paper.get("title") or "").strip()
            abstract = (paper.get("abstract") or "").strip()
            text = f"{title} {abstract}".lower()
            if not title or not abstract or not any(term in text for term in TOPIC_TERMS):
                continue
            doi = paper.get("doi", "")
            items.append(FeedItem(
                title=title,
                summary=abstract,
                link=f"https://doi.org/{doi}" if doi else "",
                published=paper.get("date", date_from),
                source_name=server,
                source_group=server,
            ))
            if len(items) >= max_results:
                break
        cursor += 100
        if cursor > 2000:  # sane cap on pagination depth per run
            break
        time.sleep(0.2)
    return items


def generate_brief(item: FeedItem, publish: bool) -> str | None:
    category = classify(item)
    key = item_id(item)
    existing = list(POSTS_DIR.glob(f"*{key[:8]}*.md"))
    if existing:
        return None

    try:
        evidence = pipeline.build_evidence_packet(client, MODEL, item.title, item.summary, item.summary, item.link)
    except Exception as exc:
        print(f"  evidence agent failed: {exc}", file=sys.stderr)
        return None

    try:
        content = pipeline.draft(client, item, category, "signal", item.summary, evidence, None)
    except Exception as exc:
        print(f"  draft failed: {exc}", file=sys.stderr)
        return None

    resources = program_resources()
    spiral = spiral_for(category, item, resources)

    published_at = dt.datetime.now(dt.timezone.utc)
    md = markdown(item, category, content, "signal", 1, published_at, None, draft=not publish, spiral=spiral)
    target = POSTS_DIR / f"historical-{item.published}-{pipeline.slug(content['headline'])}-{key[:8]}.md"
    target.write_text(md, encoding="utf-8")
    return target.name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--publish", action="store_true", help="write draft:false (default: draft:true for review)")
    parser.add_argument("--pubmed-query", default="(aging OR longevity OR senescence) AND (biophysics OR mitochondria OR metabolism)")
    parser.add_argument("--sources", default="pubmed,biorxiv", help="comma-separated: pubmed,biorxiv,medrxiv")
    parser.add_argument("--skip-novelty", action="store_true", help="generate every deduped candidate without novelty scoring")
    parser.add_argument("--overfetch", type=int, default=4, help="fetch this many candidates per --limit slot before novelty filtering")
    args = parser.parse_args()

    seen_urls = existing_source_urls()
    candidates: list[FeedItem] = []

    sources = args.sources.split(",")
    per_source = max(1, (args.limit * args.overfetch) // len(sources))

    if "pubmed" in sources:
        print(f"Fetching PubMed: {args.pubmed_query!r} {args.start}..{args.end}")
        candidates.extend(fetch_pubmed(args.pubmed_query, args.start, args.end, per_source))
    if "biorxiv" in sources:
        print(f"Fetching bioRxiv {args.start}..{args.end}")
        candidates.extend(fetch_biorxiv("biorxiv", args.start, args.end, per_source))
    if "medrxiv" in sources:
        print(f"Fetching medRxiv {args.start}..{args.end}")
        candidates.extend(fetch_biorxiv("medrxiv", args.start, args.end, per_source))

    candidates = [c for c in candidates if c.link and c.link not in seen_urls]
    print(f"\n{len(candidates)} new candidates after dedup.")

    if not args.skip_novelty and candidates:
        recent_titles = [
            re.search(r'title:\s*"(.*?)"', p.read_text(encoding="utf-8")).group(1)
            for p in sorted(POSTS_DIR.glob("*.md"))[-60:]
            if re.search(r'title:\s*"(.*?)"', p.read_text(encoding="utf-8"))
        ]
        # novelty_editor's response budget (2200 tokens, shared with the daily
        # pipeline) can't fit a full score object for 90+ candidates in one call
        # — it silently falls back to the cruder deterministic heuristic when
        # that happens. Chunking keeps every batch well inside that budget
        # regardless of how large --overfetch makes the candidate pool.
        CHUNK = 20
        NOVELTY_RETRIES = 3
        all_scores: dict[str, dict] = {}
        modes = []
        print(f"Scoring {len(candidates)} candidates against the novelty editor (min {NOVELTY_MIN_SCORE}), in chunks of {CHUNK}...")
        for i in range(0, len(candidates), CHUNK):
            chunk = candidates[i : i + CHUNK]
            # Observed 2026-08-10: a chunk well within the token budget still
            # occasionally falls back (nondeterministic — same pattern seen all
            # session in the antecedents and evidence_position calls). A plain
            # retry resolves it almost every time rather than silently accepting
            # the cruder deterministic heuristic for that chunk.
            novelty = None
            for attempt in range(NOVELTY_RETRIES):
                novelty = novelty_editor(client, MODEL, chunk, [], recent_titles, NOVELTY_MIN_SCORE)
                if novelty["mode"] == "agent":
                    break
            modes.append(novelty["mode"])
            all_scores.update(novelty["scores"])
        print(f"  novelty editor modes across chunks: {modes}")
        scored = [
            (c, all_scores.get(article_id(c.link), {}).get("score", 0))
            for c in candidates
        ]
        scored.sort(key=lambda pair: -pair[1])
        passed = [(c, s) for c, s in scored if s >= NOVELTY_MIN_SCORE]
        print(f"  {len(passed)} of {len(candidates)} cleared the novelty bar (>= {NOVELTY_MIN_SCORE}); "
              f"{len(candidates) - len(passed)} held back for reading like familiar coverage.\n")
        candidates = [c for c, _ in passed]

    candidates = candidates[: args.limit]
    print(f"Generating up to {len(candidates)}.\n")

    generated = 0
    for item in candidates:
        print(f"Drafting: {item.title[:80]}")
        name = generate_brief(item, publish=args.publish)
        if name:
            print(f"  ✓ wrote {name}")
            generated += 1
        else:
            print("  skipped (duplicate or failed)")

    print(f"\nDone! Generated {generated} of {len(candidates)} candidates.")


if __name__ == "__main__":
    main()
