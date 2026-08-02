# Agewell design system

## Scene and direction

Agewell is read like a beautifully made morning paper at a kitchen table in clear daylight. The interface is warm, assured, image-led, and easy to scan. It should never look like a hospital portal, supplement funnel, dashboard, or generic lifestyle magazine.

## Color strategy

The strategy is restrained and identity-led. Warm paper carries the surface, navy ink carries authority, mist separates editorial movements, and saffron marks action or sequence. Saffron is an accent, not a background wash.

All interface colors are expressed as OKLCH tokens in `src/styles/global.css`:

- `--ink`: primary text and dark fields
- `--ink-soft`: secondary long-form copy
- `--muted`: metadata and supporting labels
- `--paper`: page ground
- `--white`: elevated editorial surface
- `--saffron`: action and focus accent
- `--saffron-ink`: accessible accent text
- `--mist`: quiet editorial section ground
- `--line`: rules and dividers

## Typography

The publication uses the existing system stack deliberately: Iowan Old Style or Palatino for headlines and long-form reading, and Avenir Next or Segoe UI for navigation, metadata, and controls. Body text begins at 18px. Headlines use fluid `clamp()` scales with strong contrast between levels. Reading columns stay near 65 to 75 characters.

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
