#!/usr/bin/env python3
"""9:16 Kinetic Motion Video Reel Generator for Agewell Brief.

Generates 30fps dynamic 1080x1920 MP4 reels with:
- Breathing biophotonic light particles & pulsing golden aura
- Animated dancing audio equalizer bars
- Kinetic word highlights & high-contrast typography
- Neural voiceover via edge-tts piped into FFmpeg
"""

import os
import sys
import math
import random
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REELS_DIR = Path("public/social/reels")
REELS_DIR.mkdir(parents=True, exist_ok=True)

EDGE_TTS_BIN = "/Library/Frameworks/Python.framework/Versions/3.13/bin/edge-tts"

# Floating Biophotonic Particles
random.seed(42)
PARTICLES = [
    {"x": random.randint(100, 980), "y": random.randint(100, 1800), "size": random.randint(4, 12), "speed": random.uniform(1.2, 3.5), "alpha": random.randint(80, 200)}
    for _ in range(35)
]

def render_dynamic_frame(frame_idx, total_frames, fps, title, hook_text, cur_time, duration):
    W, H = 1080, 1920
    img = Image.new("RGBA", (W, H), (11, 15, 25, 255))

    # 1. Pulsing Golden Background Aura
    pulse = (math.sin(frame_idx * 0.08) + 1.0) / 2.0  # 0.0 to 1.0
    aura_alpha = int(25 + (pulse * 30))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_radius = int(400 + (pulse * 40))
    glow_draw.ellipse([540 - glow_radius, 960 - glow_radius, 540 + glow_radius, 960 + glow_radius], fill=(217, 119, 6, aura_alpha))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # 2. Drifting Biophotonic Particles
    particle_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(particle_layer)
    for p in PARTICLES:
        py = (p["y"] - (frame_idx * p["speed"])) % H
        px = p["x"] + int(math.sin((frame_idx + p["x"]) * 0.05) * 15)
        p_draw.ellipse([px - p["size"], py - p["size"], px + p["size"], py + p["size"]], fill=(245, 158, 11, p["alpha"]))
    img = Image.alpha_composite(img, particle_layer)
    draw = ImageDraw.Draw(img)

    # Fonts
    try:
        font_pill = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 28)
        font_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Georgia.ttf", 54)
        font_body = ImageFont.truetype("/System/Library/Fonts/Supplemental/Georgia.ttf", 40)
        font_cta = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 36)
    except Exception:
        font_pill = font_title = font_body = font_cta = ImageFont.load_default()

    # 3. Top Brand Badge Pill (Gold Border)
    pill_w, pill_h = 600, 70
    pill_x, pill_y = (W - pill_w) // 2, 200
    draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h], radius=35, fill=(245, 158, 11, 40), outline=(245, 158, 11, 220), width=2)
    draw.text((W // 2, pill_y + 35), "AGEWELL BRIEF · SPIRAL BIOPHYSICS", font=font_pill, fill=(247, 245, 240, 255), anchor="mm")

    # 4. Main Title Header (Saffron Gold)
    draw.text((W // 2, 380), title, font=font_title, fill=(245, 158, 11, 255), anchor="mm")

    # 5. Glassmorphism Body Card
    card_w, card_h = 900, 800
    card_x, card_y = (W - card_w) // 2, 520
    card_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card_overlay)
    card_draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=24, fill=(255, 255, 255, 18), outline=(245, 158, 11, 100), width=2)
    img = Image.alpha_composite(img, card_overlay)
    draw = ImageDraw.Draw(img)

    # 6. Kinetic Subtitle Highlight Calculation
    words = hook_text.split(" ")
    progress = min(1.0, cur_time / max(0.1, duration - 2.5))
    active_word_idx = int(progress * len(words))

    lines = []
    current_line = []
    word_positions = []
    for idx, word in enumerate(words):
        current_line.append((idx, word))
        test_str = " ".join([w for _, w in current_line])
        bbox = draw.textbbox((0, 0), test_str, font=font_body)
        if bbox[2] - bbox[0] > card_w - 120:
            current_line.pop()
            lines.append(current_line)
            current_line = [(idx, word)]
    if current_line:
        lines.append(current_line)

    start_y = card_y + 130
    for i, line_tuples in enumerate(lines):
        line_str = " ".join([w for _, w in line_tuples])
        line_y = start_y + (i * 68)
        
        # Check if line contains active word
        has_active = any(idx == active_word_idx for idx, _ in line_tuples)
        if has_active:
            # Highlight active line in gold glow
            draw.text((W // 2, line_y), line_str, font=font_body, fill=(245, 158, 11, 255), anchor="mm")
        else:
            draw.text((W // 2, line_y), line_str, font=font_body, fill=(255, 251, 235, 230), anchor="mm")

    # 7. Animated Dancing Equalizer Bars at bottom of card
    eq_y = card_y + card_h - 70
    bar_width = 16
    bar_gap = 12
    num_bars = 12
    total_eq_w = (num_bars * bar_width) + ((num_bars - 1) * bar_gap)
    start_eq_x = (W - total_eq_w) // 2

    for b in range(num_bars):
        h_factor = math.sin((frame_idx * 0.25) + (b * 0.7)) * 0.5 + 0.5
        bar_h = int(10 + (h_factor * 40))
        bx = start_eq_x + (b * (bar_width + bar_gap))
        draw.rounded_rectangle([bx, eq_y - bar_h, bx + bar_width, eq_y], radius=4, fill=(245, 158, 11, 220))

    # 8. Bottom CTA Button
    cta_w, cta_h = 840, 110
    cta_x, cta_y = (W - cta_w) // 2, 1480
    
    # Pulse CTA scale slightly
    cta_pulse = int(math.sin(frame_idx * 0.1) * 3)
    cta_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cta_draw = ImageDraw.Draw(cta_overlay)
    cta_draw.rounded_rectangle([cta_x - cta_pulse, cta_y - cta_pulse, cta_x + cta_w + cta_pulse, cta_y + cta_h + cta_pulse], radius=20, fill=(217, 119, 6, 255))
    img = Image.alpha_composite(img, cta_overlay)
    draw = ImageDraw.Draw(img)
    draw.text((W // 2, cta_y + 55), "DOWNLOAD 6 FIELD GUIDES (PDF)", font=font_cta, fill=(255, 255, 255, 255), anchor="mm")

    return img.convert("RGB")

def generate_reel(slug="living-waters-transport", title="Why Transport Comes First", hook_text="Before attempting deep cellular clearing, liquid water reorganizes into Exclusion Zone water. The skin is not where you end—it is where you exchange.", voice="en-US-AvaNeural"):
    print(f"🎬 Rendering 30 FPS Dynamic Video Reel: {title}...")

    audio_path = REELS_DIR / f"{slug}_voiceover.mp3"
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

    # 2. Get Audio Duration via ffprobe
    duration_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    dur_res = subprocess.run(duration_cmd, check=True, capture_output=True, text=True)
    duration = float(dur_res.stdout.strip())
    fps = 30
    total_frames = int(duration * fps)
    print(f"  ⏱️ Duration: {duration:.2f}s | Total Frames @ 30 FPS: {total_frames}")

    # 3. Launch FFmpeg Process Piping RAW RGB Frames
    print("  🎞️ Pipelining 30 FPS raw motion frames into FFmpeg...")
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1080x1920",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "pipe:0",
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(output_mp4)
    ]

    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    for frame_idx in range(total_frames):
        cur_time = frame_idx / fps
        frame_img = render_dynamic_frame(frame_idx, total_frames, fps, title, hook_text, cur_time, duration)
        proc.stdin.write(frame_img.tobytes())

        if (frame_idx + 1) % 60 == 0 or frame_idx == total_frames - 1:
            print(f"    • Rendered frame {frame_idx + 1}/{total_frames} ({(frame_idx+1)/total_frames*100:.1f}%)")

    proc.stdin.close()
    proc.wait()

    print(f"\n✨ 30 FPS Dynamic Video Reel successfully created: {output_mp4} ({output_mp4.stat().st_size} bytes)")
    return output_mp4

if __name__ == "__main__":
    generate_reel()
