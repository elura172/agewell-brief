"""Pull real historical studies from PubMed and bioRxiv/medRxiv and run them
through the same drafting pipeline as the daily edition (evidence packet,
autoresearch antecedents, evidence_position classification, spiral routing).

Usage:
    python3 -m scripts.historical_backfill --start 2026-08-22 --end 2026-11-07 --weekly-per-slice 5 --balanced-spirals --publish
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agewell.pipeline as pipeline
from agewell.agents import article_id, novelty_editor
from agewell.editorial import verify_category
from agewell.pipeline import (
    FeedItem,
    NOVELTY_MIN_SCORE,
    classify,
    item_id,
    markdown,
    program_resources,
    spiral_for,
)
from openai import OpenAI

POSTS_DIR = ROOT / "content/posts"

api_key = pipeline.GEMINI_API_KEY or pipeline.DEEPSEEK_API_KEY or os.environ.get("OPENAI_API_KEY", "")
client = OpenAI(api_key=api_key, base_url=pipeline.LLM_BASE_URL)
MODEL = pipeline.MODEL

TOPIC_TERMS = [
    "aging", "ageing", "longevity", "lifespan", "healthspan", "senescence", "senolytic",
    "mitochondri", "metabolic", "glucose", "insulin", "microbiome", "gut", "sleep",
    "circadian", "cognitive", "memory", "brain", "dementia", "alzheimer", "inflammation",
    "biophoton", "exclusion zone", "ez water", "epigenetic", "autophagy", "telomere",
    "glymphatic", "lymphatic", "microplastic", "heavy metal",
]

SPIRAL_PUBMED_QUERIES = [
    # 01 Living Waters
    '("glymphatic"[Title/Abstract] OR "lymphatic"[Title/Abstract] OR "vascular"[Title/Abstract] OR "bile acid"[Title/Abstract]) AND ("aging"[Title/Abstract] OR "clearance"[Title/Abstract] OR "longevity"[Title/Abstract])',
    # 02 Inner Garden
    '("gut microbiome"[Title/Abstract] OR "butyrate"[Title/Abstract] OR "short-chain fatty"[Title/Abstract] OR "intestinal barrier"[Title/Abstract]) AND ("aging"[Title/Abstract] OR "healthspan"[Title/Abstract] OR "inflammation"[Title/Abstract])',
    # 03 Higher Flame
    '("mitochondria"[Title/Abstract] OR "mitochondrial"[Title/Abstract] OR "metabolic flexibility"[Title/Abstract] OR "AMPK"[Title/Abstract]) AND ("aging"[Title/Abstract] OR "longevity"[Title/Abstract] OR "muscle"[Title/Abstract])',
    # 04 Luminous Mind
    '("slow-wave sleep"[Title/Abstract] OR "circadian"[Title/Abstract] OR "neuroplasticity"[Title/Abstract] OR "BDNF"[Title/Abstract]) AND ("cognitive"[Title/Abstract] OR "brain aging"[Title/Abstract] OR "dementia"[Title/Abstract])',
    # 05 Cell Shedding
    '("cellular senescence"[Title/Abstract] OR "senolytic"[Title/Abstract] OR "autophagy"[Title/Abstract] OR "proteostasis"[Title/Abstract]) AND ("aging"[Title/Abstract] OR "longevity"[Title/Abstract])',
    # 06 Dark Mirror
    '("microplastics"[Title/Abstract] OR "heavy metals"[Title/Abstract] OR "environmental"[Title/Abstract] OR "oxidative stress"[Title/Abstract]) AND ("aging"[Title/Abstract] OR "neurodegeneration"[Title/Abstract])',
]

_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def existing_source_urls() -> set[str]:
    urls = set()
    for p in POSTS_DIR.glob("*.md"):
        text = p.read_text(encoding="utf-8")
        m = re.search(r'source_url:\s*"(.*?)"', text)
        if m:
            urls.add(m.group(1))
    return urls


def _pubmed_month_to_number(raw: str) -> str:
    raw = raw.strip().lower()
    if raw.isdigit():
        return raw.zfill(2)
    return _MONTHS.get(raw[:3], "01")


def _extract_pubmed_date(article: ET.Element, fallback_date: str) -> str:
    # Prefer electronic <ArticleDate> first because it reliably carries exact Year/Month/Day
    for node_path in (".//ArticleDate", ".//JournalIssue/PubDate", ".//PubDate"):
        el = article.find(node_path)
        if el is None:
            continue
        y_el = el.find("Year")
        m_el = el.find("Month")
        d_el = el.find("Day")
        if y_el is not None and y_el.text and m_el is not None and m_el.text and d_el is not None and d_el.text:
            year = y_el.text.strip()
            month = _pubmed_month_to_number(m_el.text)
            day = d_el.text.strip().zfill(2)
            return f"{year}-{month}-{day}"
    return fallback_date


def fetch_pubmed(query: str, date_from: str, date_to: str, max_results: int) -> list[FeedItem]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    search_params = urllib.parse.urlencode({
        "db": "pubmed",
        "term": query,
        "datetype": "edat",
        "mindate": date_from.replace("-", "/"),
        "maxdate": date_to.replace("-", "/"),
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    })
    with urllib.request.urlopen(f"{base}/esearch.fcgi?{search_params}", timeout=30) as r:
        ids = json.loads(r.read())["esearchresult"].get("idlist", [])
    if not ids:
        return []
    time.sleep(0.35)

    fetch_params = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "xml"})
    with urllib.request.urlopen(f"{base}/efetch.fcgi?{fetch_params}", timeout=30) as r:
        root = ET.fromstring(r.read())

    items = []
    for idx, article in enumerate(root.findall(".//PubmedArticle")):
        title_el = article.find(".//ArticleTitle")
        abstract_els = article.findall(".//AbstractText")
        pmid_el = article.find(".//PMID")
        if title_el is None or not abstract_els or pmid_el is None:
            continue
        title = "".join(title_el.itertext()).strip()
        abstract = " ".join("".join(a.itertext()).strip() for a in abstract_els).strip()
        if not title or len(abstract) < 180:
            continue
        pmid = pmid_el.text.strip()

        # Spread fallback date inside [date_from, date_to] if exact day missing
        d0 = dt.date.fromisoformat(date_from)
        d1 = dt.date.fromisoformat(date_to)
        span = max(1, (d1 - d0).days + 1)
        fallback = (d0 + dt.timedelta(days=idx % span)).isoformat()
        published = _extract_pubmed_date(article, fallback)
        if published < date_from or published > date_to:
            published = fallback

        items.append(FeedItem(
            title=title,
            summary=abstract,
            link=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            published=published,
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
            if not title or len(abstract) < 180 or not any(term in text for term in TOPIC_TERMS):
                continue
            doi = paper.get("doi", "")
            pub_date = paper.get("date", date_from)
            if pub_date < date_from or pub_date > date_to:
                pub_date = date_from
            items.append(FeedItem(
                title=title,
                summary=abstract,
                link=f"https://doi.org/{doi}" if doi else "",
                published=pub_date,
                source_name=server,
                source_group=server,
            ))
            if len(items) >= max_results:
                break
        cursor += 100
        if cursor > 1200:
            break
        time.sleep(0.2)
    return items


def generate_brief(item: FeedItem, publish: bool, prefix_historical: bool = False) -> str | None:
    category = classify(item)
    key = item_id(item)
    existing = list(POSTS_DIR.glob(f"*{key[:8]}*.md"))
    if existing:
        return None

    try:
        verified = verify_category(client, MODEL, item.title, item.summary, category)
        category = verified["category"]
        if not verified["on_mission"]:
            print(f"  skipped (off-mission: {verified['reason']})", flush=True)
            return None
    except Exception as exc:
        print(f"  category verification failed, using keyword match: {exc}", file=sys.stderr, flush=True)

    try:
        evidence = pipeline.build_evidence_packet(client, MODEL, item.title, item.summary, item.summary, item.link)
    except Exception as exc:
        print(f"  evidence agent failed: {exc}", file=sys.stderr, flush=True)
        return None

    try:
        content = pipeline.draft(client, item, category, "signal", item.summary, evidence, None)
    except Exception as exc:
        print(f"  draft failed: {exc}", file=sys.stderr, flush=True)
        return None

    resources = program_resources()
    spiral = spiral_for(category, item, resources)

    try:
        published_at = dt.datetime.strptime(item.published, "%Y-%m-%d").replace(
            hour=12, tzinfo=dt.timezone.utc
        )
    except ValueError:
        published_at = dt.datetime.now(dt.timezone.utc)

    md = markdown(item, category, content, "signal", 2, published_at, None, draft=not publish, spiral=spiral)
    prefix = f"historical-{item.published}" if prefix_historical else item.published
    target = POSTS_DIR / f"{prefix}-{pipeline.slug(content['headline'])}-{key[:8]}.md"
    target.write_text(md, encoding="utf-8")
    return target.name


def run_window(
    date_from: str,
    date_to: str,
    limit: int,
    sources: list[str],
    queries: list[str],
    seen_urls: set[str],
    skip_novelty: bool,
    overfetch: int,
    publish: bool,
    prefix_historical: bool,
) -> int:
    candidates: list[FeedItem] = []
    target_pool = max(limit * overfetch, 12)

    if "pubmed" in sources:
        per_q = max(3, target_pool // max(1, len(queries)))
        for q in queries:
            try:
                candidates.extend(fetch_pubmed(q, date_from, date_to, per_q))
            except Exception as exc:
                print(f"  PubMed fetch warning ({date_from}..{date_to}): {exc}", file=sys.stderr, flush=True)

    for srv in ("biorxiv", "medrxiv"):
        if srv in sources:
            try:
                candidates.extend(fetch_biorxiv(srv, date_from, date_to, max(4, target_pool // 3)))
            except Exception as exc:
                print(f"  {srv} fetch warning ({date_from}..{date_to}): {exc}", file=sys.stderr, flush=True)

    deduped: list[FeedItem] = []
    local_seen: set[str] = set()
    for c in candidates:
        if not c.link or c.link in seen_urls or c.link in local_seen:
            continue
        local_seen.add(c.link)
        deduped.append(c)

    print(f"\n=== Window {date_from} .. {date_to}: {len(deduped)} unique candidates ===", flush=True)
    if not deduped:
        return 0

    if not skip_novelty:
        recent_titles = [
            m.group(1)
            for p in sorted(POSTS_DIR.glob("*.md"))[-60:]
            if (m := re.search(r'title:\s*"(.*?)"', p.read_text(encoding="utf-8")))
        ]
        CHUNK = 20
        all_scores: dict[str, dict] = {}
        for i in range(0, len(deduped), CHUNK):
            chunk = deduped[i : i + CHUNK]
            novelty = None
            for _ in range(2):
                novelty = novelty_editor(client, MODEL, chunk, [], recent_titles, NOVELTY_MIN_SCORE)
                if novelty["mode"] == "agent":
                    break
            if novelty:
                all_scores.update(novelty["scores"])
        scored = [
            (c, all_scores.get(article_id(c.link), {}).get("score", 0))
            for c in deduped
        ]
        scored.sort(key=lambda pair: -pair[1])
        passed = [c for c, s in scored if s >= NOVELTY_MIN_SCORE]
        deduped = passed if len(passed) >= limit else [c for c, _ in scored]

    generated = 0
    for item in deduped:
        if generated >= limit:
            break
        print(f"Drafting [{item.published} · {item.source_name}]: {item.title[:76]}", flush=True)
        name = generate_brief(item, publish=publish, prefix_historical=prefix_historical)
        if name:
            seen_urls.add(item.link)
            print(f"  ✓ wrote {name}", flush=True)
            generated += 1
    return generated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=10, help="Total limit when not slicing weekly")
    parser.add_argument("--weekly-per-slice", type=int, default=0, help="If >0, slice [start..end] into 7-day windows and generate N briefs per week")
    parser.add_argument("--balanced-spirals", action="store_true", help="Rotate across all 6 Spiral PubMed queries")
    parser.add_argument("--publish", action="store_true", help="write draft:false (default: draft:true)")
    parser.add_argument("--prefix-historical", action="store_true", help="Prefix filename with historical-")
    parser.add_argument("--pubmed-query", default="(aging OR longevity OR senescence) AND (biophysics OR mitochondria OR metabolism)")
    parser.add_argument("--sources", default="pubmed,biorxiv,medrxiv", help="comma-separated: pubmed,biorxiv,medrxiv")
    parser.add_argument("--skip-novelty", action="store_true")
    parser.add_argument("--overfetch", type=int, default=3)
    args = parser.parse_args()

    seen_urls = existing_source_urls()
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    queries = SPIRAL_PUBMED_QUERIES if args.balanced_spirals else [args.pubmed_query]

    total_generated = 0
    if args.weekly_per_slice > 0:
        cur = dt.date.fromisoformat(args.start)
        end_d = dt.date.fromisoformat(args.end)
        week_idx = 0
        while cur <= end_d:
            w_end = min(end_d, cur + dt.timedelta(days=6))
            # Rotate spiral queries by week so all 6 domains distribute evenly
            rotated = queries[week_idx % len(queries) :] + queries[: week_idx % len(queries)]
            total_generated += run_window(
                cur.isoformat(),
                w_end.isoformat(),
                args.weekly_per_slice,
                sources,
                rotated,
                seen_urls,
                args.skip_novelty,
                args.overfetch,
                args.publish,
                args.prefix_historical,
            )
            cur = w_end + dt.timedelta(days=1)
            week_idx += 1
    else:
        total_generated = run_window(
            args.start,
            args.end,
            args.limit,
            sources,
            queries,
            seen_urls,
            args.skip_novelty,
            args.overfetch,
            args.publish,
            args.prefix_historical,
        )

    print(f"\n✨ Historical backfill finished! Total generated: {total_generated}", flush=True)


if __name__ == "__main__":
    main()
