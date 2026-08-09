#!/usr/bin/env python3.13
"""
Agewell Brief Substack Auto-Publisher & Profile Sync Engine
Uses python-substack API to generate, format, draft, and publish daily briefs directly to agewellbrief.substack.com.
"""

import sys
import os
import json
import glob
from pathlib import Path

try:
    from substack.api import Api
except ImportError:
    print("Error: python-substack package not found. Run: pip install python-substack")
    sys.exit(1)

SUBSTACK_DOMAIN = os.getenv("SUBSTACK_DOMAIN", "agewellbrief")
SUBSTACK_EMAIL = os.getenv("SUBSTACK_EMAIL", "")
SUBSTACK_PASSWORD = os.getenv("SUBSTACK_PASSWORD", "")
SUBSTACK_SID = os.getenv("SUBSTACK_SID", "")

def get_latest_brief_path():
    brief_files = sorted(glob.glob("content/posts/*.md") + glob.glob("content/posts/*.mdx"), key=os.path.getmtime, reverse=True)
    if not brief_files:
        print("No brief files found in content/posts/")
        sys.exit(1)
    return brief_files[0]

def parse_brief_markdown(filepath):
    content = Path(filepath).read_text(encoding="utf-8")
    parts = content.split("---", 2)
    frontmatter = {}
    body = content
    if len(parts) >= 3:
        import yaml
        try:
            frontmatter = yaml.safe_load(parts[1])
            body = parts[2].strip()
        except Exception:
            body = parts[2].strip()
    
    title = frontmatter.get("title", "Agewell Brief Daily Dispatch")
    category = frontmatter.get("category", "Biophysics Intelligence")
    source_name = frontmatter.get("source_name", "Agewell Research Desk")
    source_url = frontmatter.get("source_url", "https://agewellbrief.com")
    
    # Build clean Substack Markdown Post
    substack_md = f"""# {title}

*Published by Agewell Brief · {category.upper()}*

---

> **Source Reporting**: [{source_name}]({source_url}) · [Read full web edition on Agewell Brief](https://agewellbrief.com)

{body}

---

### 🌊 Companion Field Manuals & Protocol Links
* **Living Waters Protocol**: [View Practitioner Formulation](https://ca.fullscript.com/s/spiraloflight/shop/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0NA==)
* **Luminous Mind Protocol**: [View Brain & Sleep Support](https://ca.fullscript.com/s/spiraloflight/shop/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0OA==)
* **Inner Garden Protocol**: [View Gut Mucosal Care](https://ca.fullscript.com/s/spiraloflight/shop/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ1MA==)

*Clear signals. Better questions.*
"""
    return title, substack_md

def main():
    if not SUBSTACK_SID and not (SUBSTACK_EMAIL and SUBSTACK_PASSWORD):
        print("💡 Substack Auto-Publisher Engine Ready!")
        print("Since Substack uses passwordless magic-link login, you can authenticate via Session Cookie OR RSS Import:")
        print("\nOption 1: Session Cookie Auth (Passwordless)")
        print("  1. Open Chrome/Safari on agewellbrief.substack.com (where you are logged in)")
        print("  2. Open DevTools (F12 / Cmd+Opt+I) -> Application/Storage -> Cookies -> substack.sid")
        print("  3. Run:")
        print("     export SUBSTACK_SID='your_substack_sid_cookie_value'")
        print("     python3.13 scripts/substack_publisher.py --publish")
        print("\nOption 2: 100% Automated Substack RSS Importer (Zero Code)")
        print("  • Go to Substack Settings -> Import -> Import RSS Feed")
        print("  • Enter: https://agewellbrief.com/rss.xml")
        print("  • Substack will automatically publish every new Agewell Brief article!")
        print("\nLatest Brief Inspected:")
        latest_brief = get_latest_brief_path()
        title, md = parse_brief_markdown(latest_brief)
        print(f"  • Title: {title}")
        print(f"  • Source File: {latest_brief}")
        print(f"  • Substack Markdown Character Count: {len(md)} chars")
        return

    print(f"🔐 Authenticating with Substack for domain: {SUBSTACK_DOMAIN}...")
    if SUBSTACK_SID:
        api = Api(cookies={"substack.sid": SUBSTACK_SID}, publication_url=f"https://{SUBSTACK_DOMAIN}.substack.com")
    else:
        api = Api(email=SUBSTACK_EMAIL, password=SUBSTACK_PASSWORD, publication_url=f"https://{SUBSTACK_DOMAIN}.substack.com")
    
    latest_brief = get_latest_brief_path()
    title, md = parse_brief_markdown(latest_brief)
    
    print(f"📝 Creating Substack draft from '{latest_brief}'...")
    draft = api.create_draft_from_markdown(md, title=title)
    print(f"✨ Draft created successfully! Draft ID: {draft}")
    
    if "--publish" in sys.argv:
        print("🚀 Publishing draft directly to Substack...")
        res = api.publish_draft(draft["id"])
        print(f"🎉 Post published live on agewellbrief.substack.com! Result: {res}")
    else:
        print("📌 Draft saved on Substack. Run with '--publish' flag to auto-publish instantly.")

if __name__ == "__main__":
    main()
