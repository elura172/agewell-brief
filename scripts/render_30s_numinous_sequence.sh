#!/bin/bash
# Agewell Brief: 30-Second Numinous Film Sequence Renderer
# Renders 6 synchronized 5-second shots using Higgsfield Seedance 2.0 CLI

set -e
mkdir -p public/social/reels/30s_sequence/

echo "🎬 Starting 30-Second Numinous Master Film Rendering..."
echo "  • Total Shots: 6 Shots (5 seconds each)"
echo "  • Target Aspect Ratio: 9:16 (1080x1920 @ 30 FPS)"
echo "  • Directorial Engine: Seedance 2.0 (Emily2040/seedance-2.0)"
echo ""

# Shot 01: Living Waters
echo "🌊 [Shot 01/06] Rendering Living Waters (EZ Water H3O2 Liquid Crystal)..."
higgsfield generate create seedance_2_0_mini \
  --prompt "Macro 9:16 vertical shot. Viscous liquid crystal water forming an ordered hexagonal Exclusion Zone structure over a dark teal glass membrane. Bioluminescent silver-teal light caustics refract slowly through the fluid. Slow controlled dolly push-in from medium close-up to tight macro, 85mm shallow depth of field. High biophotonic clarity, 30 fps." \
  --aspect_ratio 9:16 --wait

# Shot 02: Inner Garden
echo "🌱 [Shot 02/06] Rendering Inner Garden (Microbial SCFA Mucosal Wall)..."
higgsfield generate create seedance_2_0_mini \
  --prompt "Microscopic 9:16 vertical cinematic shot of a living gut mucosal barrier. Epithelial cells stand aligned like crystalline pillars while golden amber SCFA molecules float softly into tight-junction channels. Low-angle horizontal tracking slider move, 50mm natural lens perspective. Rich golden amber and moss-green bioluminescent soil, 30 fps." \
  --aspect_ratio 9:16 --wait

# Shot 03: Cell Shedding
echo "🍃 [Shot 03/06] Rendering Cell Shedding (Senolytic Autophagic Renewal)..."
higgsfield generate create seedance_2_0_mini \
  --prompt "Microscopic 9:16 vertical shot showing the selective clearance of a senescent cell. Translucent mint-green energy dissolves damaged cellular debris while surrounding healthy tissue blossoms with clear biophotonic luminescence. Slow vertical tilt-up camera move, 35mm lens feel, 30 fps." \
  --aspect_ratio 9:16 --wait

# Shot 04: Higher Flame
echo "🔥 [Shot 04/06] Rendering Higher Flame (Mitochondrial AMPK Ignition)..."
higgsfield generate create seedance_2_0_mini \
  --prompt "Macro 9:16 vertical shot of a glowing mitochondrion inside a dark cell matrix. Internal cristae folds pulse with ember-gold thermal energy, releasing a transparent gold biophotonic spiral wave. Slow centered push-in rotation, 85mm lens with volumetric light rays, 30 fps." \
  --aspect_ratio 9:16 --wait

# Shot 05: Luminous Mind
echo "⚡ [Shot 05/06] Rendering Luminous Mind (Glymphatic Delta Sleep Wash)..."
higgsfield generate create seedance_2_0_mini \
  --prompt "Microscopic 9:16 vertical shot of a glowing neural network during deep slow-wave Delta sleep. Translucent silver-blue dendrites pulse gently while clear luminous cerebrospinal fluid flows softly through brain intercellular channels. Smooth orbital crane arc tracking fluid motion, 30 fps." \
  --aspect_ratio 9:16 --wait

# Shot 06: Dark Mirror
echo "🪞 [Shot 06/06] Rendering Dark Mirror (Intracellular Mineral Balance)..."
higgsfield generate create seedance_2_0_mini \
  --prompt "Macro 9:16 vertical shot of a dark crystalline mineral lattice immersed in clear fluid. Fine copper and quartz veins pulse with subtle electrical voltage while trace mineral solutes balance the surrounding ionic field. Locked macro focus, 85mm lens, 30 fps." \
  --aspect_ratio 9:16 --wait

echo "🎉 All 6 shots generated! Check your Higgsfield account dashboard or download URLs above."
