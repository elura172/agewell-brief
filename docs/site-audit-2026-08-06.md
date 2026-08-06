# Agewell Brief — site audit, 2026-08-06

## CRITICAL — the subscribe funnel discards every signup

`src/pages/index.astro` guards the Loops calls behind `if (apiKey)` where
`apiKey = import.meta.env.PUBLIC_LOOPS_API_KEY || ""`. That var is not set in the
Cloudflare build, so Vite tree-shook the whole block away. The live minified handler is:

```js
t.disabled=!0; t.textContent="Joining...";
try{ e.style.display="none"; s.classList.remove("is-hidden") }catch{ ... }
```

It shows the success box and drops the email. No network call at all
(`grep -c "app.loops.so"` on live HTML = 0). Every subscriber since launch is gone,
with no error and no record. All CTAs funnel here: hero "Subscribe Free", the sticky
per-article bar, nav "Get the Brief", the subscribe section.

Secondary: even when the key IS set, the design ships a Loops API key to every visitor
in client JS, and the catch-all `.catch(() => {})` + unconditional success box means
failures stay invisible. Fix should move the write server-side (Cloudflare Worker route
or Loops' own hosted form), not just populate the public var.

`.env` has `LOOPS_API_KEY` (server-side name) set locally — the key exists, it was
simply never wired to a build-time public var. PostHog by contrast DOES load in prod
(hardcoded fallback in `Layout.astro`), so reader-visit telemetry is real.

## HIGH — headlines are unedited source titles

52 of 70 briefs ship the source title verbatim; only 18 were rewritten. (An earlier
count of "6/6" here was wrong — the regex missed the 64 files whose line 1 is
`---title:`.) The 18 rewrites show the mechanism works well when it fires: "Gut health
is an ecology, not a single supplement", "A sleep EEG 'brain age' score tracked future
dementia risk". Archive shows raw
academic paper titles: "Regional cerebral arterial elasticity is associated with
cardiovascular health in cognitively healthy older adults" (114 chars),
"LiteVax-adjuvanted influenza vaccine induces transient interferon-driven innate
activation...". One leaks a publisher suffix: "... - Neuroscience News".
The body prose already does the translation well ("Your brain is a vascular glutton"),
so this is purely a missing headline-rewrite step — the biggest gap between
PRODUCT.md's promise and the delivered surface.

ROOT CAUSE FOUND — the machinery exists and is pointed the wrong way.
`agewell/pipeline.py:788` already asks the model for a `headline` and honours a
per-feed `headline_mode` ("rewrite" | "preserve"). In `config/feed-portfolio.json`
the setting is inverted relative to need: `rewrite` on the 5 NIH/FDA feeds, which
already publish plain-English titles, and `preserve` on all 26 journal/preprint
feeds (arXiv, bioRxiv, medRxiv, Nature Aging, eLife, GeroScience, Frontiers) whose
titles are exactly the unreadable ones. Flipping the journal feeds to `rewrite` is a
config change, no code. Note this is TWO changes, not one: FDA/NIH are currently on
`rewrite`, so moving them to `preserve` is a real edit — worth doing, since regulatory
recall wording is the one place verbatim fidelity actually matters.

Two decisions this needs from the user, not silent defaults:
1. Is rewriting a paper's title acceptable editorially? (Standard science journalism
   says yes; the counter-argument is fidelity to the study's own claim.)
2. It only affects NEW briefs. The 49 already published keep their raw titles unless
   a backfill pass rewrites them — which would change the <h1> and <title> of 49
   live, already-indexed URLs.

## MEDIUM

- Homepage lead dek is boilerplate: "Cutting-edge research translated into actionable
  intelligence: what was discovered, why it matters..." — identical template text, not a
  real dek for the story.
- `image_caption` is the same generic string on 12 briefs: "A glimpse of the everyday
  routines behind this story." 37 briefs are `image_review_status: pending`; stock images
  are only loosely related (EEG headband photo on a cerebral-artery-elasticity study).
- "Trending this week" subtitled "Most visited briefs over the last 24 hours" —
  contradictory, and it publicly exposes 10–14 visit counts.
- Every archive item is badged `EMERGING` — the badge carries zero information.
- Unrendered LaTeX on homepage framework card: `($H_3O_2$)` in the Living Waters blurb.
- Sticky subscribe bar overlaps body copy persistently on article pages.

## LOW / latent

- 64 of 70 files in `content/posts/` open with `---title: "..."` on line 1 (delimiter and
  first key merged). Astro tolerates it today — all 49 published briefs build — but it's a
  malformed-frontmatter hazard from whatever writes these files.
- Social manifest records `success: true` with `post_id: null, url: null`, so published
  posts have no click-through audit trail.

## Already fixed this session
- venv rebuilt (daily pulse had been dead 3 days: hybrid 3.13/3.14 venv).
- `mpt_content_runner.py` unsupported MPT subtitle args + swallowed stderr (commit 97d6891).
- Content-factory launch agent unloaded at user's request (reels on hold).
