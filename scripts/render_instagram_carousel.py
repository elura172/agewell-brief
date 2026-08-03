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

# Palette Tokens
COLOR_BG = (11, 15, 25)         # Deep Midnight
COLOR_CARD = (20, 26, 40)       # Elevated Midnight
COLOR_BORDER = (40, 50, 75)     # Subtle Line
COLOR_TEXT = (254, 254, 254)    # Pure White
COLOR_MUTED = (160, 175, 200)   # Muted Blue-Gray
COLOR_SAFFRON = (245, 158, 11)  # Solar Gold / Saffron
COLOR_CYAN = (0, 240, 255)      # Quantum Cyan

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

def draw_card(title: str, category: str, slide_num: int, total_slides: int, heading: str, body_text: str, accent_color=COLOR_SAFFRON):
    W, H = 1080, 1350
    img = Image.new("RGB", (W, H), COLOR_BG)
    draw = ImageDraw.Draw(img)

    # 1. Background Gradient / Subtle Border Card
    draw.rectangle([40, 40, W - 40, H - 40], fill=COLOR_CARD, outline=COLOR_BORDER, width=2)

    # 2. Top Kicker & Slide Counter
    font_kicker = get_font(28, bold=True)
    font_counter = get_font(28)
    
    kicker_text = f"AGEWELL BRIEF  ·  {category.upper()}"
    draw.text((80, 80), kicker_text, fill=accent_color, font=font_kicker)
    
    counter_text = f"{slide_num}/{total_slides}"
    draw.text((W - 140, 80), counter_text, fill=COLOR_MUTED, font=font_counter)

    # 3. Decorative Accent Line
    draw.line([(80, 130), (W - 80, 130)], fill=COLOR_BORDER, width=1)

    # 4. Slide Heading
    font_heading = get_font(52, bold=True)
    wrapped_heading = textwrap.fill(heading, width=24)
    draw.text((80, 180), wrapped_heading, fill=COLOR_TEXT, font=font_heading)

    # 5. Slide Body Text
    font_body = get_font(36)
    wrapped_body = textwrap.fill(body_text, width=36)
    
    # Calculate Y position after heading
    bbox = draw.textbbox((80, 180), wrapped_heading, font=font_heading)
    body_y = bbox[3] + 50
    
    draw.text((80, body_y), wrapped_body, fill=COLOR_MUTED, font=font_body)

    # 6. Bottom Footer / Brand & Swipe Indicator
    draw.line([(80, H - 140), (W - 80, H - 140)], fill=COLOR_BORDER, width=1)
    font_footer = get_font(26)
    
    draw.text((80, H - 100), "AgewellBrief.com  ·  Source-Led Biophysics", fill=COLOR_MUTED, font=font_footer)
    if slide_num < total_slides:
        draw.text((W - 220, H - 100), "Swipe →", fill=accent_color, font=font_footer)
    else:
        draw.text((W - 320, H - 100), "Link in Bio ↗", fill=accent_color, font=font_footer)

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
