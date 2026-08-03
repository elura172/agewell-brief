import glob
import json
import os
import re
from pathlib import Path
from openai import OpenAI
import agewell.pipeline
from agewell.agents import autoresearch_context_subagent, copy_edit

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content/posts"

api_key = os.getenv("DEEPSEEK_API_KEY")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

AI_BOILERPLATE_PATTERNS = [
    r"A connection is context, not proof\.?",
    r"Each frontier is followed for what it clarifies, what it challenges, and what still needs to be measured\.?",
    r"Curiosity without collapse\.?",
    r"Only time will tell\.?",
    r"While more research is needed before drawing firm conclusions,? ",
    r"More research is needed before drawing definitive conclusions\.?",
    r"It remains to be seen whether these findings translate to humans\.?",
]

def clean_ai_boilerplate(text: str) -> str:
    cleaned = text
    for pattern in AI_BOILERPLATE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

def process_file(filepath: Path):
    content = filepath.read_text(encoding="utf-8")
    
    # Clean up superficial AI boilerplate
    cleaned_content = clean_ai_boilerplate(content)
    
    if cleaned_content != content:
        filepath.write_text(cleaned_content, encoding="utf-8")
        print(f"Purged AI boilerplate from {filepath.name}")

def main():
    post_files = list(POSTS_DIR.glob("*.md"))
    print(f"Auditing {len(post_files)} articles in content/posts/...\n")
    
    updated_count = 0
    for filepath in post_files:
        content = filepath.read_text(encoding="utf-8")
        original = content
        
        # Check if AI boilerplate present
        has_boilerplate = any(re.search(pat, content, re.I) for pat in AI_BOILERPLATE_PATTERNS)
        if has_boilerplate:
            content = clean_ai_boilerplate(content)
            filepath.write_text(content, encoding="utf-8")
            print(f"  ⚡ Cleaned AI boilerplate in: {filepath.name}")
            updated_count += 1
            
    print(f"\nCompleted archive audit! Cleaned {updated_count} files.")

if __name__ == "__main__":
    main()
