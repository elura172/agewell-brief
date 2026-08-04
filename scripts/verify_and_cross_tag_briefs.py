#!/usr/bin/env python3
"""Audit and cross-tag all biophysics briefs with multi-topic & multi-framework tags.

Scans all post markdown files in content/posts/ and analyzes body copy for relevant
cross-disciplinary topics (e.g. brain health, sleep health, metabolic health, gut health,
cellular senescence, detoxification, longevity) and tags them into `topics` frontmatter array.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content/posts"

TOPIC_KEYWORDS = {
    "brain health": ["brain", "cognitive", "alzheimer", "dementia", "memory", "neural", "glymphatic", "synapse", "fmri"],
    "sleep health": ["sleep", "circadian", "melatonin", "rhythm", "night", "rest"],
    "gut health": ["gut", "microbiome", "microbial", "microbiota", "short-chain fatty acid", "scfa", "intestine"],
    "metabolic health": ["metabolic", "metabolism", "mitochondria", "glucose", "insulin", "lactate", "fasting", "atp", "respiration"],
    "cellular senescence": ["senescence", "senolytic", "zombie cell", "sasp", "chromatin", "autophagy", "cell-free"],
    "detoxification": ["detox", "chelation", "heavy metal", "clearing", "mineral", "zeolite", "kidney", "liver"],
    "longevity": ["aging", "biological age", "healthspan", "longevity", "lifespan", "mortality"],
    "mobility": ["balance", "proprioception", "motor", "exercise", "strength", "biomechanics", "muscle"],
    "consumer safety": ["fda", "tainted", "adulterated", "warning", "recall", "drug"]
}

FRAMEWORK_MAP = {
    "brain health": "Luminous Mind",
    "sleep health": "Luminous Mind",
    "gut health": "Inner Garden",
    "metabolic health": "Higher Flame",
    "cellular senescence": "Cell Shedding",
    "detoxification": "Dark Mirror",
    "longevity": "Living Waters",
    "mobility": "Living Waters"
}

def audit_file(filepath: Path) -> bool:
    text = filepath.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False

    frontmatter = parts[1]
    body = parts[2]

    # Parse primary category
    cat_match = re.search(r'category:\s*"(.*?)"', frontmatter)
    primary_cat = cat_match.group(1).lower() if cat_match else "general wellness"

    # Analyze body + title for matching topics
    full_text = text.lower()
    matched_topics = set([primary_cat])

    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in full_text for kw in keywords):
            matched_topics.add(topic)

    topics_list = sorted(list(matched_topics))
    frameworks_list = sorted(list(set(FRAMEWORK_MAP[t] for t in topics_list if t in FRAMEWORK_MAP)))

    # Check if already tagged properly
    topics_fm = f"topics: {topics_list}"
    frameworks_fm = f"frameworks: {frameworks_list}"

    if "topics:" in frontmatter and "frameworks:" in frontmatter:
        # Update existing
        frontmatter = re.sub(r'topics:.*', topics_fm, frontmatter)
        frontmatter = re.sub(r'frameworks:.*', frameworks_fm, frontmatter)
    else:
        # Append to frontmatter
        frontmatter = frontmatter.strip() + f"\n{topics_fm}\n{frameworks_fm}\n"

    updated_file = f"---{frontmatter}---{body}"
    filepath.write_text(updated_file, encoding="utf-8")
    return True

def main():
    files = sorted(list(POSTS_DIR.glob("*.md")))
    print(f"🏷️ Auditing and cross-tagging {len(files)} biophysics briefs...\n")

    updated = 0
    for f in files:
        if audit_file(f):
            updated += 1

    print(f"✅ Successfully verified and cross-tagged {updated} briefs with multi-topic biophysics frameworks!")

if __name__ == "__main__":
    main()
