import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content/posts"
MIND_OCEAN_VAULT = Path("/Users/mirrr/mind-ocean/vault/agewell-brief")

def slugify(text: str) -> str:
    return re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "-")

def sync_agewell_to_mind_ocean():
    if not MIND_OCEAN_VAULT.parent.exists():
        print("❌ Mind Ocean directory not found at /Users/mirrr/mind-ocean/")
        return

    MIND_OCEAN_VAULT.mkdir(parents=True, exist_ok=True)
    (MIND_OCEAN_VAULT / "Historical Antecedents").mkdir(exist_ok=True)
    (MIND_OCEAN_VAULT / "Frontier Territories").mkdir(exist_ok=True)
    (MIND_OCEAN_VAULT / "Topics").mkdir(exist_ok=True)

    print(f"🌊 Syncing Agewell Brief corpus into Mind Ocean vault ({MIND_OCEAN_VAULT})...\n")

    posts = list(POSTS_DIR.glob("*.md"))
    synced_count = 0

    for filepath in posts:
        content = filepath.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue

        frontmatter_raw = parts[1]
        body = parts[2]

        title_match = re.search(r'title:\s*"(.*?)"', frontmatter_raw)
        category_match = re.search(r'category:\s*"(.*?)"', frontmatter_raw)
        evidence_match = re.search(r'evidence_position:\s*"(.*?)"', frontmatter_raw)

        if not title_match:
            continue

        title = title_match.group(1)
        category = category_match.group(1) if category_match else "general wellness"
        evidence_pos = evidence_match.group(1) if evidence_match else "emerging"

        # Extract AutoResearch antecedents if present
        antecedents = []
        ant_match = re.search(r"autoresearch_antecedents:\s*(\[.*?\])", frontmatter_raw)
        if ant_match:
            try:
                antecedents = json.loads(ant_match.group(1))
            except Exception:
                pass

        # Build wiki links for Mind Ocean semantic topology
        wiki_links = [
            f"[[Topic - {category.title()}]]",
            f"[[Evidence - {evidence_pos.title()}]]"
        ]

        for ant in antecedents:
            scientist = ant.get("scientist", "")
            year = ant.get("year", "")
            discovery = ant.get("discovery", "")
            ant_filename = f"{scientist} - {discovery[:40]} ({year})"
            wiki_links.append(f"[[{ant_filename}]]")

            # Write historical antecedent note
            ant_filepath = MIND_OCEAN_VAULT / "Historical Antecedents" / f"{slugify(ant_filename)}.md"
            ant_note = f"""---
title: "{scientist} ({year})"
scientist: "{scientist}"
year: "{year}"
type: "historical_antecedent"
---

# {scientist} ({year})

**Discovery:** {discovery}

## Connected Modern Briefs
- [[{title}]]
"""
            ant_filepath.write_text(ant_note, encoding="utf-8")

        # Format note for Mind Ocean vault
        ocean_note_body = f"""---
title: "{title}"
category: "{category}"
evidence_position: "{evidence_pos}"
type: "agewell_brief"
---

# {title}

**Category:** [[Topic - {category.title()}]]
**Evidence Position:** [[Evidence - {evidence_pos.title()}]]

## Connected Biophysics & Lineage
{chr(10).join("- " + link for link in wiki_links)}

---

{body}
"""

        target_file = MIND_OCEAN_VAULT / filepath.name
        target_file.write_text(ocean_note_body, encoding="utf-8")
        synced_count += 1

    print(f"✨ Successfully synced {synced_count} Agewell Brief notes & historical antecedents into Mind Ocean!")

if __name__ == "__main__":
    sync_agewell_to_mind_ocean()
