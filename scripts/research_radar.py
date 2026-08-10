#!/usr/bin/env python3
"""Research Radar — mechanisms 01 and 02.

Two signal mechanisms that need no data collection beyond what every brief
already carries in frontmatter:

  01. Confidence shift within a topic — a topic tag whose briefs climb the
      speculative -> contested -> emerging -> established ladder over time.
      NOTE: this groups by topic, not by mechanism or study. Two briefs in
      the same climb are frequently different findings that happen to share
      a topic tag, not the same claim being re-confirmed — a genuine
      mechanism-level version (grouped by shared antecedent instead) was
      tested 2026-08-10 and currently returns zero hits against this
      archive, so topic-level is what ships until the archive is deep
      enough to support the stricter definition. Report copy must say so.
  02. Cross-framework citation convergence — a historical antecedent
      (Popp, Pollack, Warburg, ...) cited by briefs from three or more
      distinct categories, independently arriving at the same root mechanism.

Every entry in the output carries the exact briefs (title, date, slug,
evidence position) that produced it — nothing here is generated text. If
the archive is too young to trigger a mechanism, this reports that plainly
instead of inventing an example (see the "Dream State" mistake this spec
starts by naming: docs in the Research Radar artifact from 2026-08-09).

Usage:
    python3 -m scripts.research_radar
    python3 -m scripts.research_radar --min-categories 2   # loosen mechanism 02
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content/posts"
OUTPUT = ROOT / "src/data/research-radar.json"

# The maturation ladder mechanism 01 walks. "historical" is a separate axis
# (settled old knowledge cited for context, not a claim in progress) and is
# deliberately excluded — it doesn't climb toward established, it starts there.
LADDER = {"speculative": 0, "contested": 1, "emerging": 2, "established": 3}


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    content = text[3:]
    if not content.startswith("\n"):
        content = "\n" + content
    match = re.match(r"^\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except Exception:
        return {}


def load_briefs() -> list[dict]:
    briefs = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        fm = parse_frontmatter(path)
        if not fm or fm.get("draft"):
            continue
        date = fm.get("date")
        if isinstance(date, str):
            date = datetime.fromisoformat(date.replace("Z", "+00:00"))
        if date and date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        briefs.append({
            "slug": path.stem,
            "title": fm.get("title", path.stem),
            "date": date,
            "category": fm.get("category", "general wellness"),
            "evidence_position": fm.get("evidence_position", "emerging"),
            "frontier_vectors": fm.get("frontier_vectors") or [],
            "topics": fm.get("topics") or [],
            "antecedents": fm.get("autoresearch_antecedents") or [],
        })
    return [b for b in briefs if b["date"] is not None]


def brief_ref(b: dict) -> dict:
    return {
        "slug": b["slug"],
        "title": b["title"],
        "date": b["date"].date().isoformat(),
        "evidence_position": b["evidence_position"],
    }


def mechanism_evidence_drift(briefs: list[dict], min_drift_days: int = 7) -> list[dict]:
    """01. Which topics climbed the evidence ladder, and when.

    Groups by topic tag, not by underlying study or mechanism — a climb
    pairs whichever two briefs under that topic sit lowest/highest on the
    ladder, which are often two different findings, not one finding
    re-confirmed. Report this as "confidence shifted within a topic," never
    as "this mechanism matured."

    A "climb" only counts if the two briefs are at least min_drift_days apart.
    Without this, two same-topic briefs published hours apart at different
    evidence positions read as "drift over time" when they're really just two
    different takes on the same day — observed 2026-08-10 on an archive still
    mostly one week deep, e.g. "2026-08-02 emerging -> 2026-08-02 established".
    That's not evidence maturing, it's same-day variance.
    """
    by_vector: dict[str, list[dict]] = defaultdict(list)
    for b in briefs:
        vectors = b["frontier_vectors"] or b["topics"] or [b["category"]]
        for v in vectors:
            by_vector[v].append(b)

    entries = []
    for vector, group in by_vector.items():
        ladder_group = [b for b in group if b["evidence_position"] in LADDER]
        ladder_group.sort(key=lambda b: b["date"])
        if len(ladder_group) < 2:
            continue

        climbs = []
        high_water = -1
        high_water_brief = None
        for b in ladder_group:
            rung = LADDER[b["evidence_position"]]
            # Calendar-date subtraction, not full timestamp subtraction: two
            # briefs a real calendar year apart but at different times of day
            # (e.g. noon vs 8am) floor-divide to one day short of the true
            # gap under naive .days subtraction — caught 2026-08-10 on a
            # 367-day pair that reported as 366.
            gap_days = (b["date"].date() - high_water_brief["date"].date()).days if high_water_brief else None
            if high_water_brief is not None and rung > high_water and gap_days >= min_drift_days:
                climbs.append({
                    "from": brief_ref(high_water_brief),
                    "to": brief_ref(b),
                    "from_position": high_water_brief["evidence_position"],
                    "to_position": b["evidence_position"],
                    "gap_days": gap_days,
                })
            if rung > high_water:
                high_water = rung
                high_water_brief = b

        if climbs:
            entries.append({
                "mechanism": "evidence_drift",
                "vector": vector,
                "climb_count": len(climbs),
                "climbs": climbs,
                "brief_count": len(ladder_group),
            })

    entries.sort(key=lambda e: -e["climb_count"])
    return entries


def mechanism_citation_convergence(briefs: list[dict], min_categories: int) -> list[dict]:
    """02. Which antecedent scientists were independently cited across
    distinct categories — convergence, not just repetition."""
    by_scientist: dict[str, list[dict]] = defaultdict(list)
    for b in briefs:
        seen_this_brief = set()
        for a in b["antecedents"]:
            name = (a or {}).get("scientist")
            if not name or name in seen_this_brief:
                continue
            seen_this_brief.add(name)
            by_scientist[name].append(b)

    entries = []
    for scientist, group in by_scientist.items():
        categories = {b["category"] for b in group}
        if len(categories) < min_categories:
            continue
        ordered = sorted(group, key=lambda b: b["date"])
        entries.append({
            "mechanism": "citation_convergence",
            "scientist": scientist,
            "category_count": len(categories),
            "categories": sorted(categories),
            "briefs": [brief_ref(b) for b in ordered],
        })

    entries.sort(key=lambda e: -e["category_count"])
    return entries


def run(min_categories: int, min_drift_days: int = 7) -> dict:
    briefs = load_briefs()
    drift = mechanism_evidence_drift(briefs, min_drift_days)
    convergence = mechanism_citation_convergence(briefs, min_categories)

    dates = [b["date"] for b in briefs]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "archive_size": len(briefs),
        "archive_span": {
            "earliest": min(dates).date().isoformat() if dates else None,
            "latest": max(dates).date().isoformat() if dates else None,
        },
        "evidence_drift": drift,
        "citation_convergence": convergence,
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-categories", type=int, default=3,
                         help="minimum distinct categories for a convergence hit (default 3)")
    parser.add_argument("--min-drift-days", type=int, default=7,
                         help="minimum days between briefs for a climb to count as real drift, not same-day variance (default 7)")
    parser.add_argument("--write", action="store_true",
                         help="write output to src/data/research-radar.json (default: print only)")
    args = parser.parse_args()

    result = run(args.min_categories, args.min_drift_days)

    span = result["archive_span"]
    print(f"Archive: {result['archive_size']} briefs, {span['earliest']} to {span['latest']}")
    print(f"Evidence drift (min {args.min_drift_days}d gap): {len(result['evidence_drift'])} vector(s) climbed the ladder")
    for e in result["evidence_drift"]:
        print(f"  - {e['vector']}: {e['climb_count']} climb(s) across {e['brief_count']} briefs")
        for c in e["climbs"]:
            print(f"      {c['from']['date']} {c['from_position']} -> {c['to']['date']} {c['to_position']} ({c['gap_days']}d)  ({c['to']['title'][:60]})")
    print(f"Citation convergence (min {args.min_categories} categories): {len(result['citation_convergence'])} scientist(s)")
    for e in result["citation_convergence"]:
        print(f"  - {e['scientist']}: {e['category_count']} categories ({', '.join(e['categories'])})")
        for b in e["briefs"]:
            print(f"      {b['date']}  {b['title'][:70]}")

    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nWrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
