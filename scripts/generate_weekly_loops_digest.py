#!/usr/bin/env python3
"""Generate a weekly Sunday Biophysics Digest as a Draft Campaign in Loops (`spiraloflight`).

Selects the top 3 published briefs from the past 7 days (weighted by Cloudflare
reader visits in `src/data/trending.json`, lead rank, and recency), pairs them
with the dominant Spiral protocol spotlight ($33/mo Monthly Cycle & $222/yr
Annual Passage), compiles Guardian-clean LMX, and creates (or updates) a Draft
Campaign in Loops targeted at non-active leads (`accessStatus != "active"`).

Usage:
  python3 scripts/generate_weekly_loops_digest.py --dry-run
  python3 scripts/generate_weekly_loops_digest.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content" / "posts"
TRENDING_FILE = ROOT / "src" / "data" / "trending.json"

THEME_ID = "cmpjigeny09910170zfn286ox"
LOGO_COMPONENT_ID = "cmpjigdob099001707iah2ohu"
LOOPS_API_BASE = "https://app.loops.so/api/v1"

SPIRAL_META: dict[str, dict[str, str]] = {
    "waters": {
        "name": "Living Waters",
        "focus": "interfacial hydration, Phase I/II hepatic conjugation, and vascular micro-transport",
        "pdf": "https://agewellbrief.com/downloads/field-guides/living-waters-field-guide.pdf",
    },
    "garden": {
        "name": "Inner Garden",
        "focus": "mucosal barrier integrity, short-chain fatty acid signaling, and vagal gut-brain tone",
        "pdf": "https://agewellbrief.com/downloads/field-guides/inner-garden-field-guide.pdf",
    },
    "flame": {
        "name": "Higher Flame",
        "focus": "mitochondrial membrane voltage, AMPK insulin sensitivity, and substrate switching",
        "pdf": "https://agewellbrief.com/downloads/field-guides/higher-flame-field-guide.pdf",
    },
    "mind": {
        "name": "Luminous Mind",
        "focus": "slow-wave N3 sleep, astrocyte AQP4 glymphatic clearance, and BDNF neuroplasticity",
        "pdf": "https://agewellbrief.com/downloads/field-guides/luminous-mind-field-guide.pdf",
    },
    "shedding": {
        "name": "Cell Shedding",
        "focus": "pulsed senolytic clearing, SASP dampening, and lysosomal autophagy",
        "pdf": "https://agewellbrief.com/downloads/field-guides/cell-shedding-field-guide.pdf",
    },
    "mirror": {
        "name": "Dark Mirror",
        "focus": "ionic trace-mineral replacement, biliary flow, and enterohepatic heavy-metal binding",
        "pdf": "https://agewellbrief.com/downloads/field-guides/dark-mirror-field-guide.pdf",
    },
}

NAME_TO_SLUG = {
    "living waters": "waters",
    "inner garden": "garden",
    "higher flame": "flame",
    "luminous mind": "mind",
    "cell shedding": "shedding",
    "dark mirror": "mirror",
}


def xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def attr_escape(text: str) -> str:
    return xml_escape(text).replace('"', "&quot;")


def parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, flags=re.DOTALL)
    if not match:
        return {}, raw
    fm_block, body = match.group(1), match.group(2)
    meta: dict[str, str] = {}
    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body


def clean_excerpt(body: str, fallback: str = "") -> str:
    if fallback:
        return fallback.strip()
    for para in body.split("\n\n"):
        p = para.strip()
        if not p or p.startswith("#") or p.startswith(">") or p.startswith("-"):
            continue
        p = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", p)
        p = re.sub(r"[*_`]", "", p)
        return p[:240].rsplit(" ", 1)[0] + ("…" if len(p) > 240 else "")
    return ""


def load_trending_visits() -> dict[str, int]:
    if not TRENDING_FILE.exists():
        return {}
    try:
        payload = json.loads(TRENDING_FILE.read_text(encoding="utf-8"))
        return {
            str(item["slug"]): int(item.get("visits", 0))
            for item in payload.get("articles", [])
            if item.get("slug")
        }
    except Exception:
        return {}


def select_weekly_briefs(window_days: int = 7, limit: int = 3) -> list[dict[str, str]]:
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=window_days)
    visits_map = load_trending_visits()
    candidates: list[tuple[float, dict[str, str]]] = []
    all_recent: list[tuple[dt.datetime, dict[str, str]]] = []

    for md_path in POSTS_DIR.glob("*.md"):
        raw = md_path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)
        if meta.get("draft", "").lower() == "true":
            continue
        raw_date = meta.get("date", "")
        try:
            pub_dt = dt.datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=dt.timezone.utc)
        except Exception:
            continue

        slug = md_path.stem
        spiral_raw = meta.get("spiral", "Living Waters").strip()
        spiral_slug = NAME_TO_SLUG.get(spiral_raw.lower(), "waters")
        record = {
            "slug": slug,
            "title": meta.get("title", slug),
            "description": clean_excerpt(body, meta.get("description", "")),
            "category": meta.get("category", "longevity"),
            "source_name": meta.get("source_name", "Primary study"),
            "spiral_slug": spiral_slug,
            "spiral_name": SPIRAL_META[spiral_slug]["name"],
            "url": f"https://agewellbrief.com/brief/{slug}/?utm_source=loops&utm_medium=email&utm_campaign=sunday_digest",
            "date_iso": pub_dt.strftime("%b %d"),
        }
        all_recent.append((pub_dt, record))

        if pub_dt >= cutoff:
            visits = visits_map.get(slug, 0)
            is_lead = 1 if meta.get("content_type") == "lead" else 0
            recency = (pub_dt - cutoff).total_seconds() / 86400.0
            score = (visits * 10.0) + (is_lead * 6.0) + recency
            candidates.append((score, record))

    if len(candidates) >= limit:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in candidates[:limit]]

    all_recent.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in all_recent[:limit]]


def build_digest_lmx(briefs: list[dict[str, str]], date_label: str) -> tuple[str, str, str, str]:
    spiral_counts = Counter(b["spiral_slug"] for b in briefs)
    top_slug = spiral_counts.most_common(1)[0][0] if spiral_counts else "waters"
    sp = SPIRAL_META[top_slug]

    walk_monthly = attr_escape(
        f"https://spiraloflight.life/walk?lens=biophysics&spiral={top_slug}&plan=monthly"
        f"&utm_source=loops&utm_medium=email&utm_campaign=sunday_digest"
    )
    walk_annual = attr_escape(
        f"https://spiraloflight.life/walk?lens=biophysics&spiral={top_slug}&plan=annual"
        f"&utm_source=loops&utm_medium=email&utm_campaign=sunday_digest"
    )
    pdf_href = attr_escape(sp["pdf"])

    lead_title = briefs[0]["title"] if briefs else "This week in longevity biophysics"
    subject = f"Sunday Biophysics Brief: {lead_title[:58]}" + ("…" if len(lead_title) > 58 else "")
    preview = f"Three source-linked longevity signals plus this week's {sp['name']} protocol note."

    brief_blocks: list[str] = []
    for idx, b in enumerate(briefs, start=1):
        brief_blocks.extend([
            f'<H3 paddingTop="10" paddingBottom="4">{idx}. {xml_escape(b["title"])}</H3>',
            f'<Paragraph fontSize="13" color="#64748b" paddingBottom="6">{xml_escape(b["category"].upper())} · {xml_escape(b["source_name"])} · Lens: {xml_escape(b["spiral_name"])}</Paragraph>',
            f'<Paragraph paddingBottom="8">{xml_escape(b["description"])}</Paragraph>',
            f'<Paragraph paddingBottom="14"><Link href="{attr_escape(b["url"])}">Read the full source-linked brief →</Link></Paragraph>',
        ])
        if idx < len(briefs):
            brief_blocks.append('<Divider paddingTop="4" paddingBottom="8" />')

    lmx_lines = [
        f'<Style themeId="{THEME_ID}" bodyXPadding="28" bodyYPadding="28" />',
        f'<Component componentId="{LOGO_COMPONENT_ID}" />',
        f'<Paragraph fontSize="12" color="#64748b" paddingTop="6" paddingBottom="4">SUNDAY BIOPHYSICS DIGEST · {xml_escape(date_label.upper())}</Paragraph>',
        '<H1 paddingTop="4" paddingBottom="10">Three Signals Worth Carrying Into the Week</H1>',
        '<Paragraph paddingBottom="12">Hi {contact.firstName},</Paragraph>',
        '<Paragraph paddingBottom="16">Here are the three clearest peer-reviewed longevity and cellular biophysics dispatches from the Agewell Brief desk this week—paired with the physiological sequence that connects them.</Paragraph>',
        *brief_blocks,
        '<Paragraph fontSize="12" lineHeight="100"><Br /></Paragraph>',
        '<Section blockColor="#f8fafc" blockBorderRadius="8" paddingTop="18" paddingBottom="18" paddingLeft="20" paddingRight="20">',
        f'  <H2 paddingBottom="8">Companion Protocol Spotlight: {xml_escape(sp["name"])}</H2>',
        f'  <Paragraph paddingBottom="12">Several of this week\'s findings converge on <Strong>{xml_escape(sp["name"])}</Strong>—{xml_escape(sp["focus"])}. Reading individual studies clarifies what changes; circadian sequencing determines whether your tissues can actually clear and adapt.</Paragraph>',
        f'  <Paragraph paddingBottom="14">You can download the <Link href="{pdf_href}">4-page {xml_escape(sp["name"])} Field Guide (PDF)</Link> at no cost, or step directly into the calibrated <Strong>28-Day Circadian Protocol Workspace</Strong> ($33/month cycle or $222/year four-season Annual Passage—save 44%):</Paragraph>',
        f'  <Button href="{walk_monthly}" bgColor="#111827" textColor="#ffffff" borderRadius="6" innerXPadding="20" innerYPadding="12" paddingTop="4" paddingBottom="10" align="left">Start 28-Day {xml_escape(sp["name"])} Protocol ($33/mo)</Button>',
        f'  <Paragraph fontSize="13" paddingTop="4">Or explore the <Link href="{walk_annual}">four-season Annual Passage ($222/yr)</Link> across all six spirals.</Paragraph>',
        '</Section>',
        '<Paragraph fontSize="14" paddingTop="18">Clear signals and steady rhythm,<Br /><Strong>Agewell Brief &amp; Spiral of Cellular Light</Strong></Paragraph>',
    ]
    return "\n".join(lmx_lines), subject, preview, top_slug


def http_loops(api_key: str, method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{LOOPS_API_BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "AgewellBrief-WeeklyDigest/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def create_via_http_api(api_key: str, campaign_name: str, subject: str, preview: str, lmx: str) -> dict:
    existing = http_loops(api_key, "GET", "/campaigns?perPage=20")
    for item in existing.get("data", []):
        if item.get("name") == campaign_name and item.get("status") == "Draft":
            em_id = item["emailMessageId"]
            em_current = http_loops(api_key, "GET", f"/email-messages/{em_id}")
            rev = em_current["contentRevisionId"]
            upd = http_loops(api_key, "POST", f"/email-messages/{em_id}", {
                "expectedRevisionId": rev,
                "subject": subject,
                "previewText": preview,
                "fromName": "Agewell Brief · Spiral of Cellular Light",
                "fromEmail": "fire",
                "replyTo": "fire@spiraloflight.life",
                "emailFormat": "styled",
                "lmx": lmx,
                "contactPropertyFallbacks": {"firstName": "reader"},
            })
            return {"mode": "updated_existing_draft", "campaignId": item["id"], "emailMessageId": em_id, "warnings": upd.get("warnings", [])}

    created = http_loops(api_key, "POST", "/campaigns", {
        "name": campaign_name,
        "audienceFilter": {
            "match": "all",
            "conditions": [
                {
                    "type": "property",
                    "key": "accessStatus",
                    "operator": "notEquals",
                    "value": "active",
                }
            ],
        },
    })
    camp_id = created["id"]
    em_id = created["emailMessageId"]
    rev = created["emailMessageContentRevisionId"]
    upd = http_loops(api_key, "POST", f"/email-messages/{em_id}", {
        "expectedRevisionId": rev,
        "subject": subject,
        "previewText": preview,
        "fromName": "Agewell Brief · Spiral of Cellular Light",
        "fromEmail": "fire",
        "replyTo": "fire@spiraloflight.life",
        "emailFormat": "styled",
        "lmx": lmx,
        "contactPropertyFallbacks": {"firstName": "reader"},
    })
    return {"mode": "created_draft", "campaignId": camp_id, "emailMessageId": em_id, "warnings": upd.get("warnings", [])}


def create_via_loops_cli(loops_bin: str, team: str, campaign_name: str, subject: str, preview: str, lmx: str, tmp_dir: Path) -> dict:
    def run_cli(args: list[str]) -> dict | list:
        res = subprocess.run([loops_bin, *args, "--team", team, "--output", "json"], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or res.stdout.strip())
        out = res.stdout.strip()
        first = min([i for i in (out.find("{"), out.find("[")) if i != -1], default=0)
        last = max(out.rfind("}"), out.rfind("]"))
        return json.loads(out[first : last + 1])

    filter_file = tmp_dir / "sunday-digest-filter.json"
    lmx_file = tmp_dir / "sunday-digest.lmx"
    filter_file.write_text(json.dumps({
        "match": "all",
        "conditions": [
            {
                "type": "property",
                "key": "accessStatus",
                "operator": "notEquals",
                "value": "active",
            }
        ],
    }), encoding="utf-8")
    lmx_file.write_text(lmx, encoding="utf-8")

    campaigns = run_cli(["campaigns", "list"])
    items = campaigns if isinstance(campaigns, list) else campaigns.get("data", [])
    camp_id = None
    em_id = None
    for item in items:
        if item.get("name") == campaign_name and item.get("status") == "Draft":
            camp_id = item["id"]
            em_id = item["emailMessageId"]
            break

    mode = "updated_existing_draft"
    if not camp_id:
        mode = "created_draft"
        created = run_cli([
            "campaigns", "create",
            "--name", campaign_name,
            "--audience-filter-file", str(filter_file),
        ])
        assert isinstance(created, dict)
        camp_id = created["id"]
        em_id = created["emailMessageId"]

    upd = run_cli([
        "email-messages", "update", str(em_id),
        "--force",
        "--subject", subject,
        "--preview-text", preview,
        "--from-name", "Agewell Brief · Spiral of Cellular Light",
        "--from-email", "fire",
        "--reply-to", "fire@spiraloflight.life",
        "--email-format", "styled",
        "--contact-fallback", "firstName=reader",
        "--lmx-file", str(lmx_file),
    ])
    guardian = run_cli(["email-messages", "guardian", str(em_id)])
    return {
        "mode": mode,
        "campaignId": camp_id,
        "emailMessageId": em_id,
        "warnings": upd.get("warnings", []) if isinstance(upd, dict) else [],
        "guardian": guardian,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a weekly Sunday Biophysics Digest Draft Campaign in Loops.")
    parser.add_argument("--dry-run", action="store_true", help="Print compiled LMX and metadata without calling Loops.")
    parser.add_argument("--team", default="spiral", help="Loops CLI team profile when LOOPS_API_KEY is not set.")
    parser.add_argument("--window-days", type=int, default=7)
    args = parser.parse_args()

    today = dt.datetime.now(dt.timezone.utc).date()
    date_label = today.strftime("%b %d, %Y")
    campaign_name = f"Sunday Biophysics Digest — {today.isoformat()}"

    briefs = select_weekly_briefs(window_days=args.window_days, limit=3)
    if not briefs:
        print("No published briefs found to include in digest.")
        return 0

    lmx, subject, preview, top_slug = build_digest_lmx(briefs, date_label)

    if args.dry_run:
        print(json.dumps({
            "campaignName": campaign_name,
            "subject": subject,
            "previewText": preview,
            "spotlightSpiral": top_slug,
            "briefSlugs": [b["slug"] for b in briefs],
        }, indent=2))
        print("\n--- LMX ---\n")
        print(lmx)
        return 0

    api_key = os.environ.get("LOOPS_API_KEY", "").strip()
    loops_bin = shutil.which("loops") or "/Users/mirrr/.local/bin/loops"

    if api_key:
        result = create_via_http_api(api_key, campaign_name, subject, preview, lmx)
    elif Path(loops_bin).exists():
        tmp_dir = ROOT / ".state" / "loops-digest"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        result = create_via_loops_cli(loops_bin, args.team, campaign_name, subject, preview, lmx, tmp_dir)
    else:
        print("Skipping Loops draft creation: neither LOOPS_API_KEY nor `loops` CLI is configured.")
        return 0

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
