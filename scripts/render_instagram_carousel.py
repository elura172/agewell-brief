#!/usr/bin/env python3
"""Render 1080x1350 (4:5 portrait) high-resolution Instagram Carousel PNG slide cards.

Generates 5 slide images per article:
1. Cover / Hook
2. The Core Research Discovery
3. The Biophysics Mechanism
4. Practical Functional Takeaway
5. CTA & Lead Magnet Unlock (6 PDF Guides)
"""

import json
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / ".state/social/carousels"
LATEST_SOCIAL = ROOT / ".state/social/latest.json"

# Palette Tokens & Prismatic Accents
COLOR_BG = (9, 12, 22)             # Deep Midnight Ocean
COLOR_CARD = (17, 23, 38)          # Crystalline Glass Panel
COLOR_BORDER = (45, 60, 90)        # Outer Prism Line
COLOR_PRISM_CYAN = (0, 240, 255)   # Electric Cyan
COLOR_PRISM_GOLD = (245, 158, 11)  # Solar Gold / Saffron
COLOR_PRISM_VIOLET = (168, 85, 247) # Biophotonic Violet
COLOR_PRISM_EMERALD = (16, 185, 129)# Emerald Biophysics
COLOR_TEXT = (254, 254, 254)       # Luminous White
COLOR_MUTED = (165, 180, 210)      # Star Dust Blue

CATEGORY_COLORS = {
    "brain health": COLOR_PRISM_CYAN,
    "sleep health": COLOR_PRISM_CYAN,
    "gut health": COLOR_PRISM_EMERALD,
    "metabolic health": COLOR_PRISM_GOLD,
    "cellular senescence": COLOR_PRISM_GOLD,
    "longevity": (249, 115, 22),     # Amber Renewal
    "detoxification": COLOR_PRISM_VIOLET,
}

def get_font(size: int, bold: bool = False):
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf"
    ]
    for p in font_paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_card(title: str, category: str, slide_num: int, total_slides: int, heading: str, body_text: str):
    W, H = 1080, 1350
    img = Image.new("RGB", (W, H), COLOR_BG)
    draw = ImageDraw.Draw(img)

    accent_color = CATEGORY_COLORS.get(category.lower(), COLOR_PRISM_CYAN)

    # 1. Outer Midnight Canvas Background & Glassmorphic Main Card
    draw.rectangle([40, 40, W - 40, H - 40], fill=COLOR_CARD, outline=COLOR_BORDER, width=2)

    # 2. Prismatic Iridescent Inner Border Aura (Shiny Dual-Glow Accent Lines)
    draw.rectangle([44, 44, W - 44, H - 44], outline=accent_color, width=3)
    draw.rectangle([48, 48, W - 48, H - 48], outline=COLOR_PRISM_VIOLET, width=1)

    # 3. Top Shiny Glassmorphic Kicker Badge
    font_kicker = get_font(26, bold=True)
    font_counter = get_font(26, bold=True)
    
    kicker_text = f"✨ AGEWELL BRIEF  ·  {category.upper()}"
    # Shiny Pill Background behind Kicker
    draw.rounded_rectangle([75, 75, 580, 125], radius=14, fill=(28, 38, 62), outline=accent_color, width=1)
    draw.text((95, 87), kicker_text, fill=accent_color, font=font_kicker)
    
    # Counter Badge Pill
    counter_text = f"SLIDE {slide_num} / {total_slides}"
    draw.rounded_rectangle([W - 250, 75, W - 75, 125], radius=14, fill=(28, 38, 62), outline=COLOR_BORDER, width=1)
    draw.text((W - 230, 87), counter_text, fill=COLOR_MUTED, font=font_counter)

    # 4. Prismatic Divider Line with Biophotonic Sigil Nodes
    draw.line([(80, 155), (W - 80, 155)], fill=accent_color, width=2)
    # Glowing sigil nodes at ends
    draw.ellipse([74, 149, 86, 161], fill=COLOR_PRISM_CYAN)
    draw.ellipse([W - 86, 149, W - 74, 161], fill=COLOR_PRISM_GOLD)

    # 5. Slide Heading (Luminous Typography)
    font_heading = get_font(52, bold=True)
    wrapped_heading = textwrap.fill(heading, width=24)
    draw.text((80, 205), wrapped_heading, fill=COLOR_TEXT, font=font_heading)

    # 6. Slide Body Text (Crisp Crystalline Readability)
    font_body = get_font(35)
    wrapped_body = textwrap.fill(body_text, width=36)
    
    bbox = draw.textbbox((80, 205), wrapped_heading, font=font_heading)
    body_y = bbox[3] + 45
    
    # Body Background Container Box
    draw.rounded_rectangle([75, body_y - 20, W - 75, H - 180], radius=16, fill=(24, 32, 52), outline=COLOR_BORDER, width=1)
    draw.text((105, body_y + 10), wrapped_body, fill=COLOR_TEXT, font=font_body)

    # 7. Bottom Footer / Prismatic Brand & Call-To-Action
    draw.line([(80, H - 145), (W - 80, H - 145)], fill=COLOR_BORDER, width=1)
    font_footer = get_font(26, bold=True)
    
    draw.text((80, H - 105), "🌐 AgewellBrief.com  ·  Prismatic Cosmic Biophysics", fill=COLOR_MUTED, font=font_footer)
    if slide_num < total_slides:
        draw.text((W - 240, H - 105), "SWIPE →", fill=accent_color, font=font_footer)
    else:
        draw.text((W - 320, H - 105), "✨ LINK IN BIO ↗", fill=COLOR_PRISM_GOLD, font=font_footer)

    return img

def render_article_carousel(article_data: dict) -> list[Path]:
    article_id = article_data.get("article", "brief")
    title = article_data.get("content_record", {}).get("title", "Biophysics Brief")
    category = article_data.get("category", "Biophysics")
    carousel_info = article_data.get("instagram_carousel", {})
    slides = carousel_info.get("slides", [])

    if not slides:
        # Fallback 5 slides
        slides = [
            {"heading": title, "body": "A deep biophysics breakdown into cellular coherence and longevity."},
            {"heading": "The Core Finding", "body": "Recent clinical evidence reveals new biomarkers governing cellular health."},
            {"heading": "Biophysics Mechanism", "body": "Cellular respiration and biophotonic photon trapping coordinate biological vitality."},
            {"heading": "Functional Takeaway", "body": "Align daily environmental rhythms with cellular light for sustained healthspan."},
            {"heading": "Unlock 6 Field Guides", "body": "Visit AgewellBrief.com to download 6 free Biophysics Field Guides."}
        ]

    out_dir = OUTPUT_DIR / article_id
    out_dir.mkdir(parents=True, exist_ok=True)
    
    rendered_paths = []
    total = len(slides)
    for idx, slide in enumerate(slides, start=1):
        heading = slide.get("heading", slide.get("slide_title", f"Slide {idx}"))
        body = slide.get("body", slide.get("content", ""))
        img = draw_card(title, category, idx, total, heading, body)
        out_path = out_dir / f"slide_{idx}.png"
        img.save(out_path, "PNG")
        rendered_paths.append(out_path)

    print(f"  ✓ Rendered {len(rendered_paths)} carousel slides for '{article_id}' at {out_dir}")
    return rendered_paths

def main():
    if not LATEST_SOCIAL.exists():
        print(f"❌ {LATEST_SOCIAL} does not exist. Run scripts.social_package first.")
        return

    data = json.loads(LATEST_SOCIAL.read_text(encoding="utf-8"))
    articles = data.get("packages", [])
    print(f"🎨 Rendering Instagram Carousels for {len(articles)} articles...\n")

    for article in articles:
        render_article_carousel(article)

    print(f"\n✅ All Instagram Carousels rendered in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
