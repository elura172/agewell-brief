#!/usr/bin/env python3
"""Publish briefs to Substack, oldest first, once each.

Substack's RSS importer is a one-time archive import, not a live sync — nothing
on their side watches agewellbrief.com. So ongoing delivery has to be pushed,
which is what this does.

The previous version published `get_latest_brief_path()` — the most recently
modified file — with no record of what had already gone out. On the aggregate
workflow's 3x daily schedule that reposted the same brief whenever no new one
landed, and only ever sent one of the three briefs generated that day. Any bulk
edit to content/posts (a headline backfill, say) also reshuffled mtime and made
"latest" meaningless. This keeps a ledger instead.

Usage:
    substack_publisher.py                  # dry run: list what would be sent
    substack_publisher.py --publish        # create and publish
    substack_publisher.py --draft-only     # create Substack drafts, do not send
    substack_publisher.py --limit 5        # cap posts this run (default 3)

Credentials come from SUBSTACK_SID (session cookie) or SUBSTACK_EMAIL plus
SUBSTACK_PASSWORD. With neither set the script explains how to get one and exits
0, so an unattended workflow step skips rather than fails.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content/posts"
STATE_FILE = ROOT / ".state/substack-published.json"
SITE = "https://agewellbrief.com"

SUBSTACK_DOMAIN = os.getenv("SUBSTACK_DOMAIN", "agewellbrief")
SUBSTACK_EMAIL = os.getenv("SUBSTACK_EMAIL", "")
SUBSTACK_PASSWORD = os.getenv("SUBSTACK_PASSWORD", "")
SUBSTACK_SID = os.getenv("SUBSTACK_SID", "")

# Commission cards are stripped from the syndicated copy, exactly as the RSS
# feed does it. The link home is the route back to the offer, and it keeps the
# programme routing in one place instead of restating it per channel.
CARD_RE = re.compile(r'<aside\b[^>]*class="[^"]*resource-card[^"]*"[\s\S]*?</aside>', re.I)
COMMERCIAL_HOSTS = ("fullscript.com", "hop.clickbank.net")
# Prose links slip past the card strip — the six programme explainers cite the
# storefront in their Source line. A commission link republished on Substack
# carries no rel="sponsored", so unlink it and keep the text; the link home
# leads to the site where the marked-up version lives.
COMMERCIAL_MD_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^)]*(?:%s)[^)]*)\)'
                                % "|".join(h.replace(".", r"\.") for h in COMMERCIAL_HOSTS))


def frontmatter_and_body(text: str) -> tuple[dict[str, str], str]:
    """Split a brief into a flat frontmatter dict and its body.

    Tolerates the "---title:" form (opening delimiter and first key on one
    line) that most briefs in this repo carry.
    """
    if text.startswith("---"):
        text = text[3:]
    head, sep, body = text.partition("\n---\n")
    if not sep:
        return {}, text
    data: dict[str, str] = {}
    for line in head.splitlines():
        m = re.match(r'^\s*([a-z_]+):\s*(.*?)\s*$', line)
        if m:
            data[m.group(1)] = m.group(2).strip().strip('"')
    return data, body.strip()


def brief_markdown(brief_id: str, fm: dict[str, str], body: str) -> str:
    """Render the Substack body: the brief, minus cards, plus a link home."""
    canonical = f"{SITE}/brief/{brief_id}/"
    clean = CARD_RE.sub("", body)
    clean = COMMERCIAL_MD_LINK.sub(r"\1", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()

    source_name = fm.get("source_name", "")
    source_url = fm.get("source_url", "")
    source_line = ""
    # The six programme explainers cite our own storefront; calling that
    # "original reporting" would be the same mislabel the site just dropped.
    if source_url and "fullscript.com" not in source_url:
        source_line = f"*Original reporting: [{source_name}]({source_url})*\n\n"

    return (
        f"{source_line}{clean}\n\n---\n\n"
        f"*Originally published on [Agewell Brief]({canonical}). "
        f"[Read the original]({canonical}) for the full sources and the field "
        f"guide for this topic.*\n"
    )


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"⚠️  {STATE_FILE} is unreadable; treating every brief as unposted")
    return {"posts": {}}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def publishable_briefs() -> list[tuple[str, dict[str, str], str]]:
    """Every non-draft brief, oldest first, so the archive goes out in order."""
    out = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        fm, body = frontmatter_and_body(path.read_text(encoding="utf-8"))
        if str(fm.get("draft", "")).lower() == "true":
            continue
        if not fm.get("title"):
            continue
        out.append((path.stem, fm, body))
    out.sort(key=lambda r: (r[1].get("date", ""), r[0]))
    return out


# Exit codes are the signal to CI. 0 covers every benign outcome — nothing to
# send, no credential configured, a transient error that the next run retries.
# Only a rejected credential exits non-zero, because that is the one state that
# never recovers on its own and needs a person.
EXIT_OK = 0
EXIT_AUTH_REJECTED = 2

AUTH_MARKERS = ("401", "403", "unauthor", "forbidden", "login", "sign in", "session", "cookie")


class AuthRejected(RuntimeError):
    """The credential exists but Substack refused it — almost always an expired sid."""


def looks_like_auth_failure(exc: Exception) -> bool:
    # TypeError/AttributeError mean this script is calling the library wrong —
    # a bug to fix here, not a credential to refresh. Without this guard a
    # signature mismatch reported itself as "credential rejected", because the
    # message happened to contain the word "cookie".
    if isinstance(exc, (TypeError, AttributeError, ImportError)):
        return False
    return any(m in f"{type(exc).__name__} {exc}".lower() for m in AUTH_MARKERS)


def build_api():
    try:
        from substack.api import Api
    except ImportError:
        print("python-substack is not installed. Run: pip install python-substack")
        sys.exit(1)
    url = f"https://{SUBSTACK_DOMAIN}.substack.com"
    try:
        if SUBSTACK_SID:
            # python-substack takes a semicolon-separated cookie string, not a
            # dict — the previous `cookies={...}` call raised TypeError, so this
            # would have failed on its first real run. Accept either a bare sid
            # value or a full cookie string pasted from DevTools.
            cookie_string = SUBSTACK_SID if "=" in SUBSTACK_SID else f"substack.sid={SUBSTACK_SID}"
            return Api(cookies_string=cookie_string, publication_url=url)
        return Api(email=SUBSTACK_EMAIL, password=SUBSTACK_PASSWORD, publication_url=url)
    except Exception as exc:
        if looks_like_auth_failure(exc):
            raise AuthRejected(str(exc)) from exc
        raise


def report_auth_rejected(pending_count: int, detail: str) -> None:
    print("\n" + "=" * 62)
    print("❌ SUBSTACK CREDENTIAL REJECTED — subscribers are not receiving briefs")
    print("=" * 62)
    print(f"   {pending_count} brief(s) are queued and will keep piling up until this is fixed.")
    print(f"   Substack said: {detail[:200]}")
    print("\n   A session cookie expires; this is the expected way it ends.")
    print("   Refresh it:")
    print("     1. Log in at agewellbrief.substack.com")
    print("     2. DevTools → Application → Cookies → copy 'substack.sid'")
    print("     3. Update the SUBSTACK_SID secret in GitHub repo settings")
    print("=" * 62)


def explain_missing_credentials(pending: list) -> None:
    print("💤 No Substack credentials set — skipping (this is not a failure).")
    print(f"   {len(pending)} brief(s) are waiting to go out.\n")
    print("   To enable, get a session cookie:")
    print("     1. Log in at agewellbrief.substack.com in your browser")
    print("     2. DevTools → Application → Cookies → copy the 'substack.sid' value")
    print("     3. Add it as the SUBSTACK_SID GitHub Actions secret")
    print("\n   Locally:  SUBSTACK_SID='...' python3 scripts/substack_publisher.py --publish")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true", help="publish, not just draft")
    ap.add_argument("--draft-only", action="store_true", help="create drafts and stop")
    ap.add_argument("--limit", type=int, default=3, help="max posts per run (default 3)")
    args = ap.parse_args()

    state = load_state()
    done = state.setdefault("posts", {})
    pending = [b for b in publishable_briefs() if b[0] not in done]

    print(f"📚 {len(done)} already sent · {len(pending)} pending")
    if not pending:
        print("✅ Substack is up to date with the site.")
        return 0

    batch = pending[: max(0, args.limit)]
    if len(pending) > len(batch):
        # Never let a cap hide work — a silent truncation reads as "all done".
        print(f"ℹ️  Sending {len(batch)} this run; {len(pending) - len(batch)} will wait for the next.")

    if not SUBSTACK_SID and not (SUBSTACK_EMAIL and SUBSTACK_PASSWORD):
        explain_missing_credentials(pending)
        for brief_id, fm, _ in batch:
            print(f"   would send: {fm.get('title', '')[:70]}")
        return 0

    if not (args.publish or args.draft_only):
        print("\n🔍 Dry run — nothing will be sent. Use --publish or --draft-only.\n")
        for brief_id, fm, body in batch:
            md = brief_markdown(brief_id, fm, body)
            print(f"   {fm.get('date', '')[:10]}  {fm.get('title', '')[:64]}  ({len(md)} chars)")
        return 0

    try:
        api = build_api()
    except AuthRejected as exc:
        report_auth_rejected(len(pending), str(exc))
        return EXIT_AUTH_REJECTED

    sent = 0
    for brief_id, fm, body in batch:
        title = fm.get("title", "Agewell Brief")
        md = brief_markdown(brief_id, fm, body)
        try:
            draft = api.create_draft_from_markdown(md, title=title)
            draft_id = draft.get("id") if isinstance(draft, dict) else draft
            if args.publish:
                api.publish_draft(draft_id)
            done[brief_id] = {
                "substack_id": draft_id,
                "title": title,
                "state": "published" if args.publish else "draft",
                "sent_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            }
            sent += 1
            print(f"   ✅ {'published' if args.publish else 'drafted'}: {title[:64]}")
        except Exception as exc:
            # A dead cookie fails every post identically, so stop rather than
            # printing the same rejection once per brief.
            if looks_like_auth_failure(exc):
                save_state(state)
                report_auth_rejected(len(pending) - sent, str(exc))
                return EXIT_AUTH_REJECTED
            print(f"   ❌ failed: {title[:56]} — {exc}")
        finally:
            # Persist after each post so a mid-run crash cannot cause a repost.
            save_state(state)

    still = len(pending) - sent
    print(f"\n{sent}/{len(batch)} sent · {still} still pending")
    # A transient failure is not worth waking anyone for; the next run retries.
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
