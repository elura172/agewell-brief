import argparse
import json
import os
import re
from pathlib import Path
from openai import OpenAI
import agewell.pipeline
from agewell.agents import autoresearch_context_subagent, copy_edit, _json_response
from agewell.pipeline import quote

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content/posts"

api_key = os.getenv("DEEPSEEK_API_KEY")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

def enrich_article(filepath: Path):
    text = filepath.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False

    frontmatter = parts[1]
    body = parts[2]

    # Parse title & category from frontmatter
    title_match = re.search(r'title:\s*"(.*?)"', frontmatter)
    category_match = re.search(r'category:\s*"(.*?)"', frontmatter)
    
    if not title_match or not category_match:
        return False
        
    title = title_match.group(1)
    category = category_match.group(1)
    
    # Check if already enriched with AutoResearch
    if "autoresearch_antecedents" in frontmatter:
        print(f"Skipping already enriched: {filepath.name}")
        return False

    print(f"Enriching with AutoResearch: {filepath.name}")
    
    # Run AutoResearch Deep Context Subagent
    deep_context = autoresearch_context_subagent(client, "deepseek-chat", title, body[:1500], category)
    
    antecedents = deep_context.get("historical_antecedents", [])
    mechanistic_bridge = deep_context.get("mechanistic_bridge", "")
    ancestral_insight = deep_context.get("ancestral_insight", "")
    
    if not antecedents and not mechanistic_bridge:
        return False
        
    # Append structured frontmatter. Same escaping as the live pipeline
    # (agewell.pipeline.quote) rather than the original's swap-to-single-quotes,
    # which could still break YAML if the model's text contained a backslash.
    antecedents_json = json.dumps(antecedents)
    new_fm_lines = [
        f"autoresearch_antecedents: {antecedents_json}",
        f'ancestral_insight: "{quote(ancestral_insight)}"'
    ]
    
    updated_fm = frontmatter.strip() + "\n" + "\n".join(new_fm_lines) + "\n"
    
    # Enrich body text if section present
    enriched_body = body
    if "## How to interpret it" in body or "### Source" in body:
        enrichment_text = f"\n\n### Historical Biophysics & Lineage\n{mechanistic_bridge}\n\n"
        if ancestral_insight:
            enrichment_text += f"**Ancestral parallel:** {ancestral_insight}\n\n"
            
        if "## How to interpret it" in enriched_body:
            enriched_body = enriched_body.replace("## How to interpret it", "## How to interpret it\n" + enrichment_text)
        elif "### Source" in enriched_body:
            enriched_body = enriched_body.replace("### Source", "## How to interpret it\n" + enrichment_text + "### Source")
            
    updated_file = f"---{updated_fm}---{enriched_body}"
    filepath.write_text(updated_file, encoding="utf-8")
    print(f"  ✓ Enriched {filepath.name} with {len(antecedents)} historical antecedents!")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                         help="enrich at most N un-enriched posts (default: all of them)")
    args = parser.parse_args()

    all_posts = sorted(POSTS_DIR.glob("*.md"))
    pending = [p for p in all_posts if "autoresearch_antecedents" not in p.read_text(encoding="utf-8")]
    targets = pending[: args.limit] if args.limit else pending
    print(f"{len(all_posts)} briefs total, {len(pending)} not yet enriched, processing {len(targets)}.\n")

    count = 0
    for p in targets:
        if enrich_article(p):
            count += 1

    print(f"\nDone! Enriched {count} of {len(targets)} attempted.")

if __name__ == "__main__":
    main()
