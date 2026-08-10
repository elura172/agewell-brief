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
            "No topic cleared the threshold this period — no pair of briefs under the same topic "
            "moved from a lower evidence position to a higher one across a gap of 7+ days.\n\n"
            "This is expected on a young or narrow archive; it is reported here rather than "
            "papered over.\n"
        )
    lines = []
    for e in drift:
        lines.append(f"### {e['vector'].title()}")
        lines.append(f"{e['climb_count']} pair(s) found across {e['brief_count']} briefs tagged with this topic.\n")
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

Every finding below traces to a dated brief in the Agewell Brief archive — click through to check it.

## Confidence Shifts Within a Topic

Pairs of briefs tagged with the same topic where the later brief sits higher on the evidence
ladder (speculative → contested → emerging → established) than the earlier one, at least 7 days
apart. This tracks a topic's confidence, not one mechanism maturing — the two briefs in a pair are
often different findings that happen to share a topic tag, not the same claim re-confirmed. Read
accordingly.

{render_drift_section(data['evidence_drift'])}

## Cross-Framework Convergence

Historical antecedents independently cited by briefs in unrelated categories — a signal that
disparate current research is converging on the same underlying mechanism.

{render_convergence_section(data['citation_convergence'])}

## Methodology

Full methodology, the evidence-position rubric, and the changelog live at
agewellbrief.com/research-radar-methodology — kept off this issue so findings aren't crowded by
process notes.
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
