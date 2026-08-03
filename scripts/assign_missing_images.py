import datetime as dt
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content/posts"
PUBLIC_IMAGES = ROOT / "public/images/editions"

# Category-specific fallback high-res Pexels images when API key is unconfigured
CATEGORY_EDITORIAL_IMAGES = {
    "brain health": {
        "url": "https://images.pexels.com/photos/3862140/pexels-photo-3862140.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
        "alt": "Abstract biophotonic neural subspace visualization",
        "photographer": "Google DeepMind / Pexels",
        "photographer_url": "https://www.pexels.com/@googledeepmind",
        "provider": "Pexels",
        "avg_color": "#1a2a3a"
    },
    "cellular senescence": {
        "url": "https://images.pexels.com/photos/11730899/pexels-photo-11730899.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
        "alt": "Microscopic cellular membrane and organelle renewal",
        "photographer": "Polina Kovaleva / Pexels",
        "photographer_url": "https://www.pexels.com/@polina-kovaleva",
        "provider": "Pexels",
        "avg_color": "#3a2a1a"
    },
    "gut health": {
        "url": "https://images.pexels.com/photos/1458302/pexels-photo-1458302.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
        "alt": "Microbiome ecology and cellular transport",
        "photographer": "Kat Smith / Pexels",
        "photographer_url": "https://www.pexels.com/@katsmith",
        "provider": "Pexels",
        "avg_color": "#1a3a2a"
    },
    "longevity": {
        "url": "https://images.pexels.com/photos/37330104/pexels-photo-37330104.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
        "alt": "Biological clock and mitochondrial vitality",
        "photographer": "RF._.studio / Pexels",
        "photographer_url": "https://www.pexels.com/@rfstudio",
        "provider": "Pexels",
        "avg_color": "#1a3a3a"
    },
    "metabolic health": {
        "url": "https://images.pexels.com/photos/5638644/pexels-photo-5638644.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
        "alt": "Mitochondrial metabolic energy dynamics",
        "photographer": "Karolina Grabowska / Pexels",
        "photographer_url": "https://www.pexels.com/@karolina-grabowska",
        "provider": "Pexels",
        "avg_color": "#3a1a1a"
    },
    "detoxification": {
        "url": "https://images.pexels.com/photos/4031693/pexels-photo-4031693.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
        "alt": "Cellular clearance and autophagic purification",
        "photographer": "Cottonbro Studio / Pexels",
        "photographer_url": "https://www.pexels.com/@cottonbro",
        "provider": "Pexels",
        "avg_color": "#2a1a3a"
    },
    "general wellness": {
        "url": "https://images.pexels.com/photos/6973090/pexels-photo-6973090.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
        "alt": "Vital healthspan practices and physical harmony",
        "photographer": "Mikhail Nilov / Pexels",
        "photographer_url": "https://www.pexels.com/@mikhail-nilov",
        "provider": "Pexels",
        "avg_color": "#2a3a2a"
    }
}

def assign_missing_images():
    posts = list(POSTS_DIR.glob("*.md"))
    updated_count = 0

    print(f"🖼️ Inspecting {len(posts)} posts for missing image frontmatter...\n")

    for filepath in posts:
        content = filepath.read_text(encoding="utf-8")
        if re.search(r"^image:\s*", content, re.MULTILINE):
            continue

        parts = content.split("---", 2)
        if len(parts) < 3:
            continue

        frontmatter_raw = parts[1]
        body = parts[2]

        category_match = re.search(r'category:\s*"(.*?)"', frontmatter_raw)
        category = category_match.group(1).lower() if category_match else "general wellness"

        image_info = CATEGORY_EDITORIAL_IMAGES.get(category, CATEGORY_EDITORIAL_IMAGES["general wellness"])

        # Inject image frontmatter attributes before end of frontmatter block
        image_frontmatter = f"""image: "{image_info['url']}"
image_alt: "{image_info['alt']}"
image_photographer: "{image_info['photographer']}"
image_photographer_url: "{image_info['photographer_url']}"
image_provider: "{image_info['provider']}"
image_avg_color: "{image_info['avg_color']}"
"""
        new_frontmatter = frontmatter_raw.strip() + "\n" + image_frontmatter
        new_content = f"--- \n{new_frontmatter}---{body}"

        filepath.write_text(new_content, encoding="utf-8")
        updated_count += 1
        print(f"  ✓ Added image to: {filepath.name} ({category})")

    print(f"\n✨ Successfully assigned missing images to {updated_count} posts!")

if __name__ == "__main__":
    assign_missing_images()
