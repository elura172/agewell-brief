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
SITE_BASE_URL = "https://agewellbrief.com"
SPIRAL_BASE_URL = "https://spiraloflight.life"

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
            f'<Paragraph fontSize="13" paddingBottom="6"><Text textColor="#64748b">{xml_escape(b["category"].upper())} · {xml_escape(b["source_name"])} · Lens: {xml_escape(b["spiral_name"])}</Text></Paragraph>',
            f'<Paragraph paddingBottom="8">{xml_escape(b["description"])}</Paragraph>',
            f'<Paragraph paddingBottom="14"><Link href="{attr_escape(b["url"])}">Read the full source-linked brief →</Link></Paragraph>',
        ])
        if idx < len(briefs):
            brief_blocks.append('<Divider paddingTop="4" paddingBottom="8" />')

    lmx_lines = [
        f'<Style themeId="{THEME_ID}" bodyXPadding="28" bodyYPadding="28" />',
        f'<Component componentId="{LOGO_COMPONENT_ID}" />',
        f'<Paragraph fontSize="12" paddingTop="6" paddingBottom="4"><Text textColor="#64748b">SUNDAY BIOPHYSICS DIGEST · {xml_escape(date_label.upper())}</Text></Paragraph>',
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


def build_digest_html_and_text(briefs: list[dict], date_label: str, top_slug: str, subject: str, preview: str) -> tuple[str, str]:
    spiral = SPIRAL_META.get(top_slug, SPIRAL_META["waters"])
    teaching_url = f"{SPIRAL_BASE_URL}/teaching/{top_slug}?lens=biophysics&spiral={top_slug}&utm_source=agewell_digest&utm_medium=email&utm_campaign=sunday_digest"
    walk_monthly_url = f"{SPIRAL_BASE_URL}/walk?lens=biophysics&spiral={top_slug}&plan=monthly&utm_source=agewell_digest&utm_medium=email&utm_campaign=sunday_digest"
    walk_annual_url = f"{SPIRAL_BASE_URL}/walk?lens=biophysics&spiral={top_slug}&plan=annual&utm_source=agewell_digest&utm_medium=email&utm_campaign=sunday_digest"
    pdf_url = spiral["pdf"] if spiral["pdf"].startswith("http") else f"{SITE_BASE_URL}/downloads/field-guides/{spiral['pdf']}"

    cards_html = []
    cards_text = []
    for idx, b in enumerate(briefs, start=1):
        b_spiral = SPIRAL_META.get(b["spiral_slug"], SPIRAL_META["waters"])
        article_url = f"{SITE_BASE_URL}/brief/{b['slug']}/?utm_source=agewell_digest&utm_medium=email&utm_campaign=sunday_digest"
        cards_html.append(
            f"""<div style="margin:0 0 22px 0;padding:18px 20px;border:1px solid #e2e8f0;background:#ffffff;">
              <p style="margin:0 0 6px 0;font-family:sans-serif;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;">
                Dispatch 0{idx} · {xml_escape(b['category'].upper())} · {xml_escape(b['source_name'])} · Spiral: {xml_escape(b_spiral['name'])}
              </p>
              <h2 style="margin:0 0 8px 0;font-family:Georgia,serif;font-size:19px;line-height:1.35;">
                <a href="{xml_escape(article_url)}" style="color:#0f172a;text-decoration:none;">{xml_escape(b['title'])}</a>
              </h2>
              <p style="margin:0 0 10px 0;font-family:Georgia,serif;font-size:15px;line-height:1.6;color:#334155;">
                {xml_escape(b['description'])}
              </p>
              <p style="margin:0;font-family:sans-serif;font-size:13px;font-weight:600;">
                <a href="{xml_escape(article_url)}" style="color:#0f766e;text-decoration:none;">Read full dispatch ({xml_escape(b['source_name'])}) →</a>
              </p>
            </div>"""
        )
        cards_text.append(
            f"0{idx}. {b['title']} ({b['category']} · {b['source_name']})\n{b['description']}\nRead: {article_url}"
        )

    html = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8" /><title>{xml_escape(subject)}</title></head>
<body style="margin:0;padding:28px 14px;background:#f8fafc;color:#0f172a;font-family:Georgia,serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{xml_escape(preview)}</div>
  <main style="max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;padding:32px 28px;">
    <p style="margin:0 0 8px 0;font-family:sans-serif;font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#64748b;">
      Agewell Brief · Sunday Biophysics Synthesis · {xml_escape(date_label)}
    </p>
    <h1 style="margin:0 0 12px 0;font-size:24px;line-height:1.28;">This Week’s Three Strongest Signals in Cellular Longevity</h1>
    <p style="margin:0 0 24px 0;font-size:15.5px;line-height:1.65;color:#334155;">
      Every Sunday, we distill the week’s peer-reviewed dispatches on cellular biophysics, metabolic resilience, and neuro-glymphatic repair—and connect them to the 28-day applied protocols inside the Spiral of Cellular Light.
    </p>
    {''.join(cards_html)}
    <div style="margin:28px 0 20px 0;padding:22px;background:#f8fafc;border:1px solid #cbd5e1;">
      <p style="margin:0 0 6px 0;font-family:sans-serif;font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#0f766e;">
        28-Day Protocol Spotlight · {xml_escape(spiral['name'])}
      </p>
      <p style="margin:0 0 14px 0;font-size:15px;line-height:1.6;color:#1e293b;">
        This week’s research converges on <strong>{xml_escape(spiral['name'])}</strong>: {xml_escape(spiral['focus'])}. Download the free 4-page printable Field Guide PDF or step directly into the 28-Day Protocol Workspace.
      </p>
      <p style="margin:0 0 12px 0;">
        <a href="{xml_escape(walk_monthly_url)}" style="display:inline-block;padding:11px 18px;background:#0f172a;color:#ffffff;text-decoration:none;font-family:sans-serif;font-size:12.5px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;border-radius:3px;">Start 28-Day {xml_escape(spiral['name'])} Workspace ($33/mo) →</a>
      </p>
      <p style="margin:0;font-family:sans-serif;font-size:12.5px;color:#475569;">
        <a href="{xml_escape(walk_annual_url)}" style="color:#0f766e;">Annual Four-Season Passage ($222/yr · Save 44%)</a> ·
        <a href="{xml_escape(pdf_url)}" style="color:#0f766e;">Free 4-Page Field Guide PDF</a> ·
        <a href="{xml_escape(teaching_url)}" style="color:#0f766e;">Open Biophysics Monograph</a>
      </p>
    </div>
    <p style="margin:20px 0 0 0;font-family:sans-serif;font-size:11.5px;color:#64748b;">
      Clear signals and steady rhythm · <a href="https://agewellbrief.com" style="color:#64748b;">agewellbrief.com</a> · <a href="https://spiraloflight.life/api/unsubscribe" style="color:#64748b;">Unsubscribe</a>
    </p>
  </main>
</body>
</html>"""

    text = "\n\n".join([
        f"AGEWELL BRIEF · SUNDAY BIOPHYSICS SYNTHESIS ({date_label})",
        subject,
        *cards_text,
        f"28-DAY PROTOCOL SPOTLIGHT: {spiral['name']}\nStart 28-Day Workspace ($33/mo): {walk_monthly_url}\nAnnual Passage ($222/yr): {walk_annual_url}\nFree 4-Page Field Guide PDF: {pdf_url}",
        "Unsubscribe: https://spiraloflight.life/api/unsubscribe",
    ])
    return html, text


def enqueue_sovereign_digest(
    supabase_url: str,
    service_key: str,
    issue_key: str,
    subject: str,
    html_body: str,
    text_body: str,
    top_slug: str,
) -> dict:
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    def sb_get(path: str) -> list:
        req = urllib.request.Request(f"{supabase_url}/rest/v1/{path}", headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    leads = sb_get("leads?select=email,name")
    intakes = sb_get("phase0_intakes?select=email,first_name")
    prefs = sb_get("email_preferences?select=email,unsubscribed_at")
    unsubscribed = {r["email"].strip().lower() for r in prefs if r.get("unsubscribed_at")}

    recipients: dict[str, str] = {}
    for row in leads:
        em = (row.get("email") or "").strip().lower()
        if em and "@" in em and em not in unsubscribed:
            recipients[em] = (row.get("name") or "").strip()
    for row in intakes:
        em = (row.get("email") or "").strip().lower()
        if em and "@" in em and em not in unsubscribed:
            recipients[em] = (row.get("first_name") or recipients.get(em, "")).strip()

    if not recipients:
        return {"mode": "sovereign_outbox", "queued": 0, "note": "No active recipients in leads/phase0_intakes yet"}

    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    rows = [
        {
            "idempotency_key": f"weekly_digest:{issue_key}:{email}",
            "recipient_email": email,
            "recipient_name": name or None,
            "sequence_name": "weekly_digest",
            "step_index": 1,
            "from_name": "Agewell Brief · Spiral of Cellular Light",
            "from_address": "sanctuary@spiraloflight.life",
            "reply_to": "elura172@proton.me",
            "subject": subject,
            "html_body": html_body,
            "text_body": text_body,
            "status": "scheduled",
            "exit_if_active": False,
            "scheduled_for": now_iso,
            "metadata": {"issue_key": issue_key, "spotlight_spiral": top_slug},
        }
        for email, name in recipients.items()
    ]

    ins_req = urllib.request.Request(
        f"{supabase_url}/rest/v1/email_outbox?on_conflict=idempotency_key",
        data=json.dumps(rows).encode("utf-8"),
        method="POST",
        headers={**headers, "Prefer": "resolution=ignore-duplicates,return=representation"},
    )
    with urllib.request.urlopen(ins_req, timeout=30) as resp:
        inserted = json.loads(resp.read().decode("utf-8"))

    # Trigger /api/email-dispatch on spiraloflight.life to drain immediately
    dispatched = None
    try:
        disp_req = urllib.request.Request(
            "https://spiraloflight.life/api/email-dispatch",
            method="POST",
            headers={"Authorization": f"Bearer {service_key}", "User-Agent": "AgewellBrief-WeeklyDigest/2.0"},
        )
        with urllib.request.urlopen(disp_req, timeout=30) as d_resp:
            dispatched = json.loads(d_resp.read().decode("utf-8"))
    except Exception as exc:
        dispatched = {"deferred": True, "detail": str(exc)}

    return {
        "mode": "sovereign_outbox",
        "recipientsFound": len(recipients),
        "newlyQueued": len(inserted),
        "dispatch": dispatched,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue and dispatch the weekly Sunday Biophysics Digest via Sovereign Supabase + Cloudflare Email Sending.")
    parser.add_argument("--dry-run", action="store_true", help="Print compiled digest HTML/text and metadata without queueing.")
    parser.add_argument("--window-days", type=int, default=7)
    args = parser.parse_args()

    today = dt.datetime.now(dt.timezone.utc).date()
    date_label = today.strftime("%b %d, %Y")
    issue_key = today.isoformat()
    campaign_name = f"Sunday Biophysics Digest — {issue_key}"

    briefs = select_weekly_briefs(window_days=args.window_days, limit=3)
    if not briefs:
        print("No published briefs found to include in digest.")
        return 0

    _, subject, preview, top_slug = build_digest_lmx(briefs, date_label)
    html_body, text_body = build_digest_html_and_text(briefs, date_label, top_slug, subject, preview)

    if args.dry_run:
        print(json.dumps({
            "campaignName": campaign_name,
            "subject": subject,
            "previewText": preview,
            "spotlightSpiral": top_slug,
            "briefSlugs": [b["slug"] for b in briefs],
        }, indent=2))
        print("\n--- TEXT BODY ---\n")
        print(text_body)
        return 0

    supabase_url = os.environ.get("SUPABASE_URL", "https://aefygdwktxpwfhswadlx.supabase.co").strip()
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not service_key:
        print("Skipping live outbox queue: SUPABASE_SERVICE_ROLE_KEY is not set.")
        return 0

    result = enqueue_sovereign_digest(
        supabase_url=supabase_url,
        service_key=service_key,
        issue_key=issue_key,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        top_slug=top_slug,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
