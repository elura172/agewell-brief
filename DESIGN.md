# Agewell design system

## Scene and direction

Agewell is read like a beautifully made morning paper at a kitchen table in clear daylight. The interface is warm, assured, image-led, and easy to scan. It should never look like a hospital portal, supplement funnel, dashboard, or generic lifestyle magazine.

## Color strategy

The strategy is restrained and identity-led (**Sunlit Mineral Broadsheet**). Warm cotton paper (`hue 82°`) carries the surface, deep obsidian-navy ink (`hue 248°`) carries authority, warm flax and travertine stone (`hue 78–80°`) handle dividers and colophon grounds without clinical hue drift, and burnished raw sienna / mineral ochre (`hue 54–64°`) marks action, sequence, and focus.

All interface colors are expressed as perceptually uniform OKLCH tokens in `src/styles/global.css`:

- `--ink`: primary display & prose ink (`oklch(0.205 0.032 248)`)
- `--ink-soft`: secondary long-form reading slate (`oklch(0.335 0.024 246)`)
- `--muted`: warm mineral metadata & supporting labels (`oklch(0.455 0.016 76)`)
- `--paper`: warm cotton page ground (`oklch(0.976 0.011 82)`)
- `--cream`: engraved colophon & slip ground (`oklch(0.952 0.016 80)`)
- `--mist`: warm flax editorial wash (`oklch(0.938 0.018 78)`)
- `--white`: sunlit ivory sheet (`oklch(0.992 0.006 84)`)
- `--line` / `--line-strong`: warm stone hairlines and Oxford double rules (`oklch(0.855 0.016 78)` / `oklch(0.76 0.02 76)`)
- `--saffron` / `--saffron-ink`: burnished mineral ochre-gold action & accessible text accent (`oklch(0.695 0.142 64)` / `oklch(0.445 0.128 54)`)

### Evening reading mode (`html[data-theme="evening"]`)

Sunlit Mineral Paper is always the default first-visit identity. Readers reading at night in low ambient light can opt into **Warm Candlelit Slate** via the masthead crescent/sun toggle (persisted in `localStorage` and restored synchronously in `<head>` with zero flash). The evening ramp reverses perceptual lightness along the same `76° to 82°` warm mineral axis (`--paper: oklch(0.175 0.01 76)`, `--cream: oklch(0.21 0.012 78)`, `--ink: oklch(0.922 0.013 82)`, `--saffron-ink: oklch(0.795 0.128 70)`), avoiding cold tech blue-grays or pure `#000`/`#fff` halation. Print output (`@media print`) always restores crisp black ink on white paper.

## Typography

The publication pairs optical-sized **Source Serif 4** (`opsz 8..60`, falling back to `Iowan Old Style` and `Palatino`) for display headlines and long-form prose with **Source Sans 3** (falling back to `Avenir Next`) for navigation, kickers, metadata, and controls. Body text begins at 18px with oldstyle proportional numerals in prose and tabular lining numerals across edition numbers, archive indices, and timestamps.

## Layout grammar

- Today’s edition is the homepage hero. Brand positioning must not delay the first story.
- The deep read receives the largest type and decisive photography.
- The two signals use unequal compositions so the edition feels art-directed rather than templated.
- Archives are indexed rows, not cards.
- Full-width mist and ink bands create major transitions.
- Rules, visible sources, and edition numbering communicate editorial discipline.

## Interaction and motion

Links retain visible focus states and at least 44px touch targets where they behave as controls. Editorial photographs may use a slight scale transition on hover. Motion uses an exponential ease and disappears under `prefers-reduced-motion`.

## Avoid

- Clinical teal-and-white healthcare branding
- Fear imagery or imagery implying a medical outcome
- Rounded SaaS cards, glass effects, gradients, or decorative metrics
- Repeated tiny kickers as section scaffolding
- Generic equal-card grids
- Hidden or visually ambiguous source attribution
- Decorative animation that competes with reading
