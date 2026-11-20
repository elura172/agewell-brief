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
    "brain health": [
        "brain", "brains", "cognitive", "cognition", "alzheimer", "dementia",
        "memory", "neural", "neuron", "neurons", "glymphatic", "synapse", "synaptic",
        "hippocampus", "hippocampal", "fmri", "neuroimaging", "parkinson",
    ],
    "sleep health": [
        "sleep", "sleeping", "asleep", "insomnia", "circadian", "melatonin",
        "slow-wave", "rem sleep", "chronotype", "slumber", "polysomnography",
    ],
    "gut health": [
        "gut", "microbiome", "microbial", "microbiota", "short-chain fatty acid",
        "scfa", "intestine", "intestinal", "colonic", "probiotic", "prebiotic",
    ],
    "metabolic health": [
        "metabolic", "metabolism", "mitochondria", "mitochondrial", "glucose",
        "insulin", "lactate", "fasting", "atp", "glycemic", "lipidomic",
    ],
    "cellular senescence": [
        "senescence", "senescent", "senolytic", "senolytics", "zombie cell",
        "zombie cells", "sasp", "chromatin", "autophagy", "autophagic",
    ],
    "detoxification": [
        "detox", "detoxification", "chelation", "heavy metal", "heavy metals",
        "zeolite", "microplastic", "microplastics", "pfas", "xenobiotic",
    ],
    "longevity": [
        "aging", "ageing", "biological age", "healthspan", "longevity",
        "lifespan", "geroscience", "centenarian",
    ],
    "mobility": [
        "balance", "proprioception", "gait", "exercise", "strength training",
        "biomechanics", "biomechanical", "sarcopenia", "skeletal muscle", "cartilage",
    ],
    "consumer safety": [
        "fda warning", "fda recall", "health fraud", "tainted", "adulterated",
        "undeclared", "product recall", "drug recall", "supplement recall",
        "product notification", "contaminated", "contamination",
    ],
}

FRAMEWORK_MAP = {
    "brain health": "Luminous Mind",
    "sleep health": "Luminous Mind",
    "gut health": "Inner Garden",
    "metabolic health": "Higher Flame",
    "cellular senescence": "Cell Shedding",
    "detoxification": "Dark Mirror",
    "consumer safety": "Dark Mirror",
    "longevity": "Living Waters",
    "mobility": "Living Waters"
}


def _keyword_matches(text: str, keyword: str) -> bool:
    return bool(re.search(rf"\b{re.escape(keyword)}\b", text))


def _extract_editorial_prose(frontmatter: str, body: str) -> str:
    title_match = re.search(r'^title:\s*"(.*?)"\s*$', frontmatter, re.MULTILINE)
    desc_match = re.search(r'^description:\s*"(.*?)"\s*$', frontmatter, re.MULTILINE)
    title = title_match.group(1) if title_match else ""
    desc = desc_match.group(1) if desc_match else ""
    cleaned_body = re.sub(r"<aside\b.*?</aside>", " ", body, flags=re.DOTALL | re.IGNORECASE)
    cleaned_body = re.sub(r"###\s+Source\b.*", " ", cleaned_body, flags=re.DOTALL)
    return f"{title} {desc} {cleaned_body}".lower()


def audit_file(filepath: Path) -> bool:
    text = filepath.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False

    frontmatter = parts[1]
    body = parts[2]

    # Parse primary category and routed spiral
    cat_match = re.search(r'category:\s*"(.*?)"', frontmatter)
    primary_cat = cat_match.group(1).lower() if cat_match else "general wellness"
    spiral_match = re.search(r'spiral:\s*"(.*?)"', frontmatter)
    routed_spiral = spiral_match.group(1).strip() if spiral_match else ""

    # Analyze editorial prose + headline/dek only (excluding stock image alt text & spiral cards)
    analysis_text = _extract_editorial_prose(frontmatter, body)
    matched_topics = set([primary_cat])

    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(_keyword_matches(analysis_text, kw) for kw in keywords):
            matched_topics.add(topic)

    topics_list = sorted(list(matched_topics))
    frameworks_set = set(FRAMEWORK_MAP[t] for t in topics_list if t in FRAMEWORK_MAP)
    if routed_spiral:
        frameworks_set.add(routed_spiral)
    frameworks_list = sorted(list(frameworks_set))

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

    # Keep canonical YAML delimiters on their own lines. Joining the split
    # pieces directly produced a tolerated-but-malformed `---title:` opener.
    updated_file = f"---\n{frontmatter.strip()}\n---\n\n{body.lstrip()}"
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
