"""Render research-radar.json into a periodic report for the Research Radar
B2B product — analyst register, every claim traceable to source briefs.

Usage:
    python3 -m scripts.research_radar_report
    python3 -m scripts.research_radar_report --period "Week of 2026-08-03"
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "src/data/research-radar.json"
OUTPUT_DIR = ROOT / ".state/research-radar-reports"

BASE_URL = "https://agewellbrief.com/brief"


def brief_link(ref: dict) -> str:
    return f"[{ref['title']}]({BASE_URL}/{ref['slug']}/)"


def render_drift_section(drift: list[dict]) -> str:
    if not drift:
        return (
            "No frontier vector cleared the drift threshold this period — no finding moved from "
            "one evidence position to a higher one across a gap of 7+ days within the archive window.\n\n"
            "This is expected on a young or narrow archive; it is reported here rather than "
            "papered over. As the archive deepens, this section is where maturation velocity "
            "becomes visible: which mechanisms are accumulating independent, higher-quality "
            "support over time, not just repeated coverage.\n"
        )
    lines = []
    for e in drift:
        lines.append(f"### {e['vector'].title()}")
        lines.append(f"{e['climb_count']} climb(s) across {e['brief_count']} briefs tracking this vector.\n")
        for c in e["climbs"]:
            lines.append(
                f"- **{c['from_position']} → {c['to_position']}**, {c['gap_days']} days apart: "
                f"{brief_link(c['from'])} ({c['from']['date']}) → {brief_link(c['to'])} ({c['to']['date']})"
            )
        lines.append("")
    return "\n".join(lines)


def render_convergence_section(convergence: list[dict]) -> str:
    if not convergence:
        return "No antecedent was independently cited across multiple categories this period.\n"
    lines = []
    for e in convergence:
        lines.append(f"### {e['scientist']}")
        lines.append(
            f"Cited independently across {e['category_count']} categories: {', '.join(e['categories'])}.\n"
        )
        for b in e["briefs"]:
            lines.append(f"- {b['date']} — {brief_link(b)}")
        lines.append("")
    return "\n".join(lines)


def render_report(data: dict, period: str) -> str:
    span = data["archive_span"]
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"""# Research Radar — {period}

*Generated {generated} · Archive: {data['archive_size']} briefs, {span['earliest']} to {span['latest']}*

Every finding below traces to specific, dated briefs in the Agewell Brief archive — click through
to the original source and evidence-position rationale. Nothing here is inferred without a citation
you can check.

## Evidence Maturation

Which mechanisms moved from a lower evidence position (speculative, emerging) to a higher one
(contested, established), with at least 7 days between the two briefs — same-day variance across
different takes on one topic doesn't count as maturation.

{render_drift_section(data['evidence_drift'])}

## Cross-Framework Convergence

Historical antecedents independently cited by briefs in unrelated categories — a signal that
disparate current research is converging on the same underlying mechanism, not that we told the
model to expect it (the prompt used to name examples; it no longer does, precisely to keep this
section honest — see the 2026-08-09 methodology note below).

{render_convergence_section(data['citation_convergence'])}

## Methodology

- **Evidence maturation** groups briefs by topic/frontier vector, sorts chronologically, and flags
  when evidence_position climbs the established/emerging/contested/speculative ladder with a real
  time gap. evidence_position is classified per brief against a published rubric (see
  agewellbrief.com/editorial-policy), not left at a schema default.
- **Citation convergence** requires two or more categories, computed from autoresearch_antecedents
  — historical scientists whose work the current finding extends or validates, identified per brief
  without prompt-suggested examples (an earlier version anchored on a handful of named scientists;
  removed 2026-08-09 after it visibly biased the output).
- Both mechanisms run against the full archive, published briefs only — draft content is excluded.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default=None, help='e.g. "Week of 2026-08-03" (default: derived from archive span)')
    args = parser.parse_args()

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    period = args.period or f"{data['archive_span']['earliest']} to {data['archive_span']['latest']}"

    report = render_report(data, period)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = OUTPUT_DIR / f"research-radar-{stamp}.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")
    print()
    print(report)


if __name__ == "__main__":
    main()
