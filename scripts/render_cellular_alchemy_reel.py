#!/usr/bin/env python3
"""Deep Cellular Alchemy 9:16 Scroll-Stopping Video Reel Generator.

Features:
- Fluid liquid motion & 432 Hz biophotonic frequency wave overlays
- Emerald Chlorophyll (#10B981) + Saffron Gold (#F59E0B) dual aura
- Concentric rotating cellular membrane rings
- Kinetic 1-3 word-pop subtitle engine with active neon glow
- Technical biophysics metric watermarks
- Neural voiceover via edge-tts (en-US-AvaNeural) piped into FFmpeg 30 FPS
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

# Floating Emerald & Gold Biophoton Particles
random.seed(108)
PARTICLES = [
    {
        "x": random.randint(80, 1000),
        "y": random.randint(100, 1820),
        "size": random.randint(3, 10),
        "speed": random.uniform(1.0, 3.2),
        "color": random.choice([(16, 185, 129), (245, 158, 11), (52, 211, 153)]),  # Emerald, Gold, Mint
        "alpha": random.randint(90, 220)
    }
    for _ in range(45)
]

def render_cellular_alchemy_frame(frame_idx, total_frames, fps, title, hook_text, cur_time, duration):
    W, H = 1080, 1920
    t = frame_idx / fps

    # 1. Base Deep Obsidian Background (#060B11)
    img = Image.new("RGBA", (W, H), (6, 11, 17, 255))

    # 2. Dual Aura: Emerald Chlorophyll (#10B981) + Saffron Gold (#F59E0B) Breathing Glow
    pulse_em = (math.sin(t * 1.5) + 1.0) / 2.0
    pulse_gold = (math.cos(t * 1.8) + 1.0) / 2.0

    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)

    # Emerald Aura (Left-Center)
    em_radius = int(450 + (pulse_em * 50))
    glow_draw.ellipse([300 - em_radius, 800 - em_radius, 300 + em_radius, 800 + em_radius], fill=(16, 185, 129, int(30 + pulse_em * 35)))

    # Gold Aura (Right-Center)
    gold_radius = int(420 + (pulse_gold * 45))
    glow_draw.ellipse([780 - gold_radius, 1100 - gold_radius, 780 + gold_radius, 1100 + gold_radius], fill=(245, 158, 11, int(25 + pulse_gold * 30)))

    img = Image.alpha_composite(img, glow_layer)
    draw = ImageDraw.Draw(img)

    # 3. 432 Hz Biophotonic Frequency Wave Overlay (Fluid Sine Lines)
    wave_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    w_draw = ImageDraw.Draw(wave_layer)

    wave_center_y = 960
    for w_idx in range(3):
        points = []
        amp = 40 + (w_idx * 25)
        freq = 0.005 + (w_idx * 0.002)
        speed_offset = t * (2.0 + w_idx * 0.8)
        color = (16, 185, 129, 60) if w_idx % 2 == 0 else (245, 158, 11, 50)
        
        for x in range(0, W + 20, 20):
            y = wave_center_y + int(math.sin(x * freq + speed_offset) * amp + math.cos(x * 0.003 - speed_offset) * (amp * 0.5))
            points.append((x, y))

        for i in range(len(points) - 1):
            w_draw.line([points[i], points[i+1]], fill=color, width=2)

    img = Image.alpha_composite(img, wave_layer)
    draw = ImageDraw.Draw(img)

    # 4. Concentric Rotating Cellular Membrane Rings
    cell_ring_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cr_draw = ImageDraw.Draw(cell_ring_layer)
    center_x, center_y = 540, 960

    for ring_r in [380, 440, 500]:
        cr_draw.ellipse([center_x - ring_r, center_y - ring_r, center_x + ring_r, center_y + ring_r], outline=(52, 211, 153, 40), width=1)

    img = Image.alpha_composite(img, cell_ring_layer)
    draw = ImageDraw.Draw(img)

    # 5. Drifting Biophotonic Particles
    p_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(p_layer)
    for p in PARTICLES:
        py = (p["y"] - (frame_idx * p["speed"])) % H
        px = p["x"] + int(math.sin((frame_idx * 0.05) + p["x"]) * 20)
        col = p["color"] + (p["alpha"],)
        p_draw.ellipse([px - p["size"], py - p["size"], px + p["size"], py + p["size"]], fill=col)
    img = Image.alpha_composite(img, p_layer)
    draw = ImageDraw.Draw(img)

    # Load Fonts
    try:
        font_tech = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 24)
        font_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Georgia.ttf", 52)
        font_kinetic = ImageFont.truetype("/System/Library/Fonts/Supplemental/Georgia.ttf", 58)
        font_cta = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 36)
    except Exception:
        font_tech = font_title = font_kinetic = font_cta = ImageFont.load_default()

    # 6. Technical Watermark Pill (Top)
    draw.text((W // 2, 180), "[ SPIRAL CELLULAR ALCHEMY · 432 HZ ]", font=font_tech, fill=(52, 211, 153, 200), anchor="mm")

    # 7. Main Title Header (Saffron Gold)
    draw.text((W // 2, 320), title, font=font_title, fill=(245, 158, 11, 255), anchor="mm")

    # 8. Kinetic 1-3 Word Pop Subtitle Engine (Center Focus)
    words = hook_text.split(" ")
    progress = min(1.0, cur_time / max(0.1, duration - 2.0))
    active_idx = int(progress * len(words))

    # Chunk words into 2-word groups
    chunks = []
    for i in range(0, len(words), 2):
        chunk_words = words[i:i+2]
        chunks.append((i, i + len(chunk_words), " ".join(chunk_words)))

    # Determine current active chunk
    current_chunk_str = chunks[0][2]
    for start_i, end_i, chunk_str in chunks:
        if start_i <= active_idx < end_i:
            current_chunk_str = chunk_str
            break

    # Render Active Kinetic Word Chunk Box
    chunk_box_w, chunk_box_h = 880, 240
    chunk_x, chunk_y = (W - chunk_box_w) // 2, 840

    c_box_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    c_box_draw = ImageDraw.Draw(c_box_layer)
    
    # Glassmorphism Emerald Card
    c_box_draw.rounded_rectangle([chunk_x, chunk_y, chunk_x + chunk_box_w, chunk_y + chunk_box_h], radius=28, fill=(16, 185, 129, 25), outline=(52, 211, 153, 160), width=2)
    img = Image.alpha_composite(img, c_box_layer)
    draw = ImageDraw.Draw(img)

    # Neon Emerald Kinetic Text Pop
    draw.text((W // 2, chunk_y + 120), f'"{current_chunk_str}"', font=font_kinetic, fill=(255, 251, 235, 255), anchor="mm")

    # 9. Technical Coordinate Subtext (Below Chunk Box)
    draw.text((W // 2, 1150), "EXCLUSION ZONE WATER (H3O2) · PHASE I/II LIVER CONJUGATION", font=font_tech, fill=(16, 185, 129, 180), anchor="mm")

    # 10. Bottom CTA Button (Emerald to Gold Gradient Pill)
    cta_w, cta_h = 840, 110
    cta_x, cta_y = (W - cta_w) // 2, 1480
    
    cta_pulse = int(math.sin(t * 3.0) * 4)
    cta_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cta_draw = ImageDraw.Draw(cta_layer)
    cta_draw.rounded_rectangle([cta_x - cta_pulse, cta_y - cta_pulse, cta_x + cta_w + cta_pulse, cta_y + cta_h + cta_pulse], radius=24, fill=(16, 185, 129, 240), outline=(245, 158, 11, 255), width=2)
    img = Image.alpha_composite(img, cta_layer)
    draw = ImageDraw.Draw(img)
    draw.text((W // 2, cta_y + 55), "GET 6 BIOPHYSICS FIELD GUIDES (PDF)", font=font_cta, fill=(255, 255, 255, 255), anchor="mm")

    return img.convert("RGB")

def generate_cellular_alchemy_reel(slug="living-waters-cellular-alchemy", title="Why Transport Comes First", hook_text="Before attempting deep cellular clearing, liquid water reorganizes into Exclusion Zone water. The skin is not where you end—it is where you exchange.", voice="en-US-AvaNeural"):
    print(f"🧪 Rendering 'Deep Cellular Alchemy' 30 FPS Reel: {title}...")

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
    print(f"  ⏱️ Duration: {duration:.2f}s | Total Motion Frames @ 30 FPS: {total_frames}")

    # 3. Launch FFmpeg Process Piping RAW RGB Frames
    print("  🎞️ Pipelining 30 FPS Deep Cellular Alchemy motion frames into FFmpeg...")
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
        "-crf", "19",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(output_mp4)
    ]

    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    for frame_idx in range(total_frames):
        cur_time = frame_idx / fps
        frame_img = render_cellular_alchemy_frame(frame_idx, total_frames, fps, title, hook_text, cur_time, duration)
        proc.stdin.write(frame_img.tobytes())

        if (frame_idx + 1) % 60 == 0 or frame_idx == total_frames - 1:
            print(f"    • Rendered frame {frame_idx + 1}/{total_frames} ({(frame_idx+1)/total_frames*100:.1f}%)")

    proc.stdin.close()
    proc.wait()

    print(f"\n✨ 'Deep Cellular Alchemy' 9:16 Reel successfully created: {output_mp4} ({output_mp4.stat().st_size} bytes)")
    return output_mp4

if __name__ == "__main__":
    generate_cellular_alchemy_reel()
