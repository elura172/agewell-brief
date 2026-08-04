#!/usr/bin/env python3
"""9:16 Vertical Video Reel Generator for Agewell Brief.

Uses Pillow for pixel-perfect 1080x1920 typography & layout,
edge-tts for neural voiceover, and FFmpeg for MP4 encoding.
"""

import os
import sys
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REELS_DIR = Path("public/social/reels")
REELS_DIR.mkdir(parents=True, exist_ok=True)

EDGE_TTS_BIN = "/Library/Frameworks/Python.framework/Versions/3.13/bin/edge-tts"

def create_reel_frame(title, hook_text, output_frame_path):
    W, H = 1080, 1920
    img = Image.new("RGBA", (W, H), (11, 15, 25, 255))
    draw = ImageDraw.Draw(img)

    # 1. Subtle Radial Glow in background
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse([140, 560, 940, 1360], fill=(217, 119, 6, 35))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # Load Fonts (System Fonts)
    try:
        font_pill = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 28)
        font_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Georgia.ttf", 56)
        font_body = ImageFont.truetype("/System/Library/Fonts/Supplemental/Georgia.ttf", 40)
        font_cta = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 36)
    except Exception:
        font_pill = font_title = font_body = font_cta = ImageFont.load_default()

    # 2. Brand Badge Pill (Top)
    pill_w, pill_h = 600, 70
    pill_x, pill_y = (W - pill_w) // 2, 200
    draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h], radius=35, fill=(245, 158, 11, 40), outline=(245, 158, 11, 200), width=2)
    draw.text((W // 2, pill_y + 35), "AGEWELL BRIEF · SPIRAL BIOPHYSICS", font=font_pill, fill=(247, 245, 240, 255), anchor="mm")

    # 3. Main Title Header (Saffron Gold)
    draw.text((W // 2, 380), title, font=font_title, fill=(245, 158, 11, 255), anchor="mm")

    # 4. Glassmorphism Card (Center Body)
    card_w, card_h = 900, 780
    card_x, card_y = (W - card_w) // 2, 520
    card_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card_overlay)
    card_draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=24, fill=(255, 255, 255, 18), outline=(245, 158, 11, 90), width=2)
    img = Image.alpha_composite(img, card_overlay)
    draw = ImageDraw.Draw(img)

    # Wrap hook text
    words = hook_text.split(" ")
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        test_str = " ".join(current_line)
        bbox = draw.textbbox((0, 0), test_str, font=font_body)
        if bbox[2] - bbox[0] > card_w - 100:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))

    # Draw Quote Lines
    start_y = card_y + 140
    for i, line in enumerate(lines):
        draw.text((W // 2, start_y + (i * 64)), line, font=font_body, fill=(255, 251, 235, 245), anchor="mm")

    # 5. Bottom CTA Button
    cta_w, cta_h = 840, 110
    cta_x, cta_y = (W - cta_w) // 2, 1480
    cta_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cta_draw = ImageDraw.Draw(cta_overlay)
    cta_draw.rounded_rectangle([cta_x, cta_y, cta_x + cta_w, cta_y + cta_h], radius=20, fill=(217, 119, 6, 255))
    img = Image.alpha_composite(img, cta_overlay)
    draw = ImageDraw.Draw(img)
    draw.text((W // 2, cta_y + 55), "DOWNLOAD 6 FIELD GUIDES (PDF)", font=font_cta, fill=(255, 255, 255, 255), anchor="mm")

    # Save PNG Frame
    img.convert("RGB").save(output_frame_path)
    print(f"  🖼️ Rendered 1080x1920 Frame: {output_frame_path}")

def generate_reel(slug="living-waters-transport", title="Why Transport Comes First", hook_text="Before attempting deep cellular clearing, liquid water reorganizes into Exclusion Zone water. The skin is not where you end—it is where you exchange.", voice="en-US-AvaNeural"):
    print(f"🎬 Rendering 9:16 Social Reel: {title}...")

    audio_path = REELS_DIR / f"{slug}_voiceover.mp3"
    frame_path = REELS_DIR / f"{slug}_frame.png"
    output_mp4 = REELS_DIR / f"{slug}_reel_916.mp4"

    full_script = f"{hook_text} Download your 6 free biophysics field guides at agewell brief dot com."

    # 1. Generate Voiceover Audio
    print("  🎙️ Generating neural voiceover audio...")
    tts_cmd = [
        EDGE_TTS_BIN,
        "--voice", voice,
        "--text", full_script,
        "--write-media", str(audio_path)
    ]
    subprocess.run(tts_cmd, check=True)

    # 2. Render 1080x1920 Frame
    create_reel_frame(title, hook_text, frame_path)

    # 3. Multiplex Frame + Audio into 9:16 MP4 via FFmpeg
    print("  🎞️ Encoding 9:16 MP4 video with FFmpeg...")
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(frame_path),
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(output_mp4)
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    print(f"\n✨ 9:16 Video Reel successfully created: {output_mp4} ({output_mp4.stat().st_size} bytes)")
    return output_mp4

if __name__ == "__main__":
    generate_reel()
