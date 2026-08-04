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
* **Living Waters Protocol**: [View Practitioner Formulation](https://ca.fullscript.com/u/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0NA==)
* **Luminous Mind Protocol**: [View Brain & Sleep Support](https://ca.fullscript.com/u/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0OA==)
* **Inner Garden Protocol**: [View Gut Mucosal Care](https://ca.fullscript.com/u/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ1MA==)

*Clear signals. Better questions.*
"""
    return title, substack_md

def main():
    if not SUBSTACK_EMAIL or not SUBSTACK_PASSWORD:
        print("💡 Substack Auto-Publisher Engine Ready!")
        print("To auto-publish daily posts to agewellbrief.substack.com, set environment variables:")
        print("  export SUBSTACK_EMAIL='your-email@proton.me'")
        print("  export SUBSTACK_PASSWORD='your-substack-password'")
        print("\nLatest Brief Inspected:")
        latest_brief = get_latest_brief_path()
        title, md = parse_brief_markdown(latest_brief)
        print(f"  • Title: {title}")
        print(f"  • Source File: {latest_brief}")
        print(f"  • Substack Markdown Character Count: {len(md)} chars")
        return

    print(f"🔐 Authenticating with Substack for domain: {SUBSTACK_DOMAIN}...")
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
