#!/usr/bin/env python3
"""Research Radar — mechanism 03 (prototype): clinical trial registry activity.

Cross-references named compounds/interventions mentioned in brief titles
against ClinicalTrials.gov (free, keyless, query.intr field) to surface
"this bench finding already has trial-registry activity" signal — the kind
of thing an institutional/VC buyer diligences that a citation graph alone
doesn't show.

STATUS: prototype, not wired into research_radar.py output yet. Extraction
is a curated compound dictionary matched against brief titles, not NER or
an LLM pass — deliberately simple so results are auditable before spending
on anything fancier. Ships nothing to the site; run manually and inspect.

Known limitation, stated plainly: the dictionary only catches compounds we
already know to look for. It will silently miss novel interventions named
in briefs we haven't added to COMPOUNDS. That's fine for a prototype whose
job is "does this correlation exist at all," not for a shipped product.

Usage:
    python3 -m scripts.trial_registry
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.research_radar import load_briefs, parse_frontmatter, POSTS_DIR  # noqa: E402
from agewell.agents import _json_response  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TERMS_CACHE = ROOT / ".state/trial-search-terms.json"

_env_path = ROOT / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# Curated, not exhaustive — proper nouns / compound names specific enough
# that query.intr on ClinicalTrials.gov returns clean, on-topic hits.
# Kept as a zero-cost fallback / sanity check against the LLM pass below.
COMPOUNDS = [
    "urolithin a", "rapamycin", "metformin", "nicotinamide riboside", "nmn",
    "resveratrol", "spermidine", "fisetin", "quercetin", "dasatinib",
    "senolytic", "taurine", "semaglutide", "klotho", "acarbose",
    "alpha-ketoglutarate", "17-alpha-estradiol", "canagliflozin", "mitoq",
    "berberine", "trimethylglycine",
]

CTGOV_URL = "https://clinicaltrials.gov/api/v2/studies"

EXTRACTOR_SYSTEM = """You extract clinical-trial search terms from science news headlines for a \
longevity/aging research desk. Given a brief's title and source title, name the single most \
specific NAMED compound, drug, or intervention class the finding is actually about — the kind of \
term that would appear in a ClinicalTrials.gov "intervention" field (e.g. "rapamycin", \
"urolithin A", "senolytic", "GLP-1 agonist", "caloric restriction").

Return JSON: {"term": "<term>"} or {"term": null} if the finding is a bench-level mechanism, \
pathway, gene, or protein with no named compound/intervention a trial would list (e.g. a paper \
about a gene switch, a signaling pathway, or a lab technique with no drug/supplement/diet attached).

Do not invent a compound that isn't actually named or clearly implied in the title. When genuinely \
unsure, return null — a missed term costs nothing; a wrong one pollutes a trial-registry lookup."""


def extract_compounds(title: str) -> list[str]:
    lower = title.lower()
    return [c for c in COMPOUNDS if c in lower]


def extract_term_llm(client, model: str, title: str, source_title: str) -> str | None:
    result = _json_response(
        client, model, EXTRACTOR_SYSTEM,
        {"title": title, "source_title": source_title},
        200,
    )
    term = result.get("term")
    return term.strip() if isinstance(term, str) and term.strip() else None


def build_client():
    from openai import OpenAI
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    if not api_key:
        raise SystemExit("No DEEPSEEK_API_KEY/OPENROUTER_API_KEY/OPENAI_API_KEY set — cannot run the LLM extraction pass.")
    return OpenAI(api_key=api_key, base_url=base_url)


def load_term_cache() -> dict[str, str | None]:
    if TERMS_CACHE.exists():
        return json.loads(TERMS_CACHE.read_text(encoding="utf-8"))
    return {}


def save_term_cache(cache: dict[str, str | None]) -> None:
    TERMS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TERMS_CACHE.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def run_extraction(force: bool = False) -> dict[str, str | None]:
    """Run (or reuse) the LLM term-extraction pass across the published archive.

    Cached to .state/trial-search-terms.json keyed by slug — this costs real
    money (~1-2c/brief) and is meant to run once, not on every invocation.
    """
    cache = {} if force else load_term_cache()
    briefs = load_briefs()
    to_run = [b for b in briefs if b["slug"] not in cache]
    if not to_run:
        return cache

    client = build_client()
    model = os.getenv("LLM_MODEL", "deepseek-v4-flash")
    fm_by_slug = {p.stem: parse_frontmatter(p) for p in POSTS_DIR.glob("*.md")}

    print(f"Extracting trial-search terms for {len(to_run)} brief(s) not yet cached...")
    for i, b in enumerate(to_run, 1):
        fm = fm_by_slug.get(b["slug"], {})
        source_title = fm.get("source_title", "")
        try:
            term = extract_term_llm(client, model, b["title"], source_title)
        except Exception as e:
            # Do not cache a null on API failure — that would look identical to a
            # real "no named intervention" verdict and silently under-report
            # coverage forever. Skip it; it stays un-cached and retries next run.
            print(f"  [{i}/{len(to_run)}] ERROR on {b['slug']} (not cached, will retry): {e}")
            continue
        cache[b["slug"]] = term
        status = term if term else "(no named intervention)"
        print(f"  [{i}/{len(to_run)}] {b['title'][:60]!r} -> {status}")

    save_term_cache(cache)
    return cache


# Above this, query.intr is matching so loosely (e.g. "exercise", "lifestyle
# intervention") that it's not really "this compound has trial activity" —
# it's "this word appears somewhere in tens of thousands of unrelated trials".
# Threshold picked empirically 2026-08-10: specific compounds (senolytic,
# urolithin a, litevax adjuvant) land in the tens; generic terms (exercise,
# statin, omega-3 fatty acids) land in the hundreds to tens of thousands.
GENERIC_TOTAL_COUNT_THRESHOLD = 150


def query_ctgov(term: str) -> dict:
    params = {
        "query.intr": term,
        "pageSize": 10,
        "format": "json",
        "countTotal": "true",
        "fields": "NCTId,BriefTitle,OverallStatus,Phase,LeadSponsorName,StartDate",
    }
    url = CTGOV_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.load(r)
    trials = []
    for s in data.get("studies", []):
        ps = s["protocolSection"]
        ident = ps.get("identificationModule", {})
        status = ps.get("statusModule", {})
        design = ps.get("designModule", {})
        sponsor = ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
        trials.append({
            "nct_id": ident.get("nctId"),
            "title": ident.get("briefTitle"),
            "status": status.get("overallStatus"),
            "phase": design.get("phases"),
            "sponsor": sponsor.get("name"),
            "start_date": status.get("startDateStruct", {}).get("date"),
        })
    return {"trials": trials, "total_count": data.get("totalCount", len(trials))}


def run(use_llm: bool = True) -> dict:
    briefs = load_briefs()
    hits_by_compound: dict[str, list[dict]] = {}

    if use_llm:
        terms = run_extraction()
        for b in briefs:
            term = (terms.get(b["slug"]) or "").strip().lower()
            if not term:
                continue
            hits_by_compound.setdefault(term, []).append({
                "slug": b["slug"], "title": b["title"], "date": b["date"].date().isoformat(),
            })
        source = "LLM-extracted terms"
    else:
        for b in briefs:
            for compound in extract_compounds(b["title"]):
                hits_by_compound.setdefault(compound, []).append({
                    "slug": b["slug"], "title": b["title"], "date": b["date"].date().isoformat(),
                })
        source = "fixed compound dictionary"

    print(f"Archive: {len(briefs)} briefs, {len(hits_by_compound)} named compound(s) found via {source}")
    for compound in hits_by_compound:
        print(f"  - {compound!r} mentioned in {len(hits_by_compound[compound])} brief(s)")

    entries = []
    for compound, briefs_matched in hits_by_compound.items():
        try:
            result = query_ctgov(compound)
        except Exception as e:
            print(f"    ERROR querying {compound!r}: {e}")
            continue
        time.sleep(0.3)  # be polite to a free, keyless public API
        total_count = result["total_count"]
        entries.append({
            "compound": compound,
            "briefs": briefs_matched,
            "trial_count": len(result["trials"]),
            "total_count": total_count,
            "specific": total_count <= GENERIC_TOTAL_COUNT_THRESHOLD,
            "trials": result["trials"],
        })

    entries.sort(key=lambda e: (not e["specific"], e["total_count"]))
    return {
        "mechanism": "trial_registry_activity",
        "status": "prototype",
        "archive_size": len(briefs),
        "term_coverage": sum(len(v) for v in hits_by_compound.values()),
        "entries": entries,
    }


OUTPUT = ROOT / "src/data/trial-registry.json"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dictionary-only", action="store_true",
                         help="skip the LLM extraction pass, use the fixed compound dictionary only (free, low coverage)")
    parser.add_argument("--refresh-terms", action="store_true",
                         help="ignore the cached .state/trial-search-terms.json and re-run extraction for every brief (costs money)")
    parser.add_argument("--write", action="store_true",
                         help="write output to src/data/trial-registry.json (default: print only)")
    args = parser.parse_args()

    if args.refresh_terms and not args.dictionary_only:
        run_extraction(force=True)

    result = run(use_llm=not args.dictionary_only)
    print()
    print(f"Coverage: {result['term_coverage']}/{result['archive_size']} briefs matched a named term "
          f"({len([e for e in result['entries'] if e['specific']])} specific enough for signal, "
          f"{len([e for e in result['entries'] if not e['specific']])} too generic)")
    for e in result["entries"]:
        active = [t for t in e["trials"] if t["status"] in ("RECRUITING", "ACTIVE_NOT_RECRUITING", "NOT_YET_RECRUITING")]
        tag = "SPECIFIC" if e["specific"] else "generic"
        print(f"\n=== [{tag}] {e['compound']} — {e['total_count']} total on ClinicalTrials.gov, {len(active)} active/recruiting ===")
        print(f"    cited in {len(e['briefs'])} brief(s): {', '.join(b['title'][:50] for b in e['briefs'][:3])}")
        for t in e["trials"][:5]:
            print(f"    {t['nct_id']}  {t['status']}  phase={t['phase']}  sponsor={t['sponsor']}")

    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nWrote {OUTPUT.relative_to(ROOT)}")
