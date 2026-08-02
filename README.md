# Agewell Brief

Standalone RSS-to-editorial-draft pipeline for a readable health and longevity digest.

For a reusable, topic-agnostic operating manual, see [WORKFLOW.md](WORKFLOW.md).

The first version intentionally produces Markdown drafts for review. It uses RSS metadata and summaries, links back to the original source, and writes structured output suitable for Hugo or Astro.

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY="..."
export PEXELS_API_KEY="..."
export PIXABAY_API_KEY="..."
export RSS_FEED_URL="https://example.com/feed.xml"
python -m agewell.pipeline
```

Optional affiliate configuration is supplied as JSON. Use encrypted HopLinks
created and tested in ClickBank's Affiliate Link Tools; the pipeline appends a
stable article-level tracking ID automatically:

```bash
export AFFILIATE_OFFERS_JSON='{"mobility":"https://YOUR_ENCRYPTED_VALUE.hop.clickbank.net"}'
```

Offers are matched by exact editorial category. The pipeline does not place a
general-wellness offer in a mobility, brain-health, metabolic-health, or
longevity article unless that category has its own reviewed HopLink. Men's
health is also routed independently, so sexual-wellness offers never spill into
unrelated health coverage. Sleep health has its own category as well, preventing
sleep offers from appearing beside dementia coverage that merely mentions sleep.

Several reviewed offers can be routed within one category using the richer
format below. `approved` is deliberately fail-closed, `priority` selects the
preferred tier, and equal-priority links rotate deterministically by article:

```bash
export AFFILIATE_OFFERS_JSON='{"offers":[{"category":"brain health","name":"Reviewed offer A","url":"https://ENCRYPTED.hop.clickbank.net","approved":true,"priority":10}]}'
```

Run `python -m scripts.check_affiliate_offers` to write a redacted technical
health report to `.state/affiliate-health.json`. The daily workflow performs
this check before drafting and suppresses links that return a recognizable
ClickBank HopLink error page. A successful redirect confirms reachability only;
each offer still needs a one-time attribution check through ClickBank's order
form and HopLink tools.

ClickBank's current APIs expose analytics, orders, seller-owned products, and
account statistics, but not a public affiliate-marketplace catalog. For that
reason Agewell does not scrape the logged-in marketplace or auto-promote an
unknown vendor. Marketplace discovery remains a reviewed onboarding step;
routing, technical checks, article-level TIDs, and later conversion reporting
are automated after approval.

Generated files land in `content/posts/`; processing state is stored in `.state/processed.json`.

## Evergreen context layer

The pipeline can optionally retrieve background passages from a private local
library. Configure directories or individual sources only on a machine that
has access to them:

```bash
export EVERGREEN_CONTEXT_SOURCES_JSON='[{"label":"Grow a New Body transcripts","path":"/Users/mirrr/Movies/grow a new body/transcripts","kind":"program_transcript"},{"label":"Spiral of Cellular Light","path":"/Users/mirrr/Desktop/spiral of cellular light","kind":"spiral_framework"}]'
python -m agewell.pipeline
```

The retriever is lexical and deterministic, so it adds no database or model
dependency. It passes only the top matching excerpts to the editor with a
strict instruction to use them as background framing—not as current medical
evidence—and records source metadata in `evergreen-context.json`. The raw
library and excerpts are never copied into the repository or its audit trail.

GitHub Actions cannot see `/Users/mirrr/...`. To use this layer in cloud runs,
provide a separately authorized private context bundle or companion repository
and point the same variables at its checked-out path. Until that is configured,
cloud editions continue normally without evergreen context.

## Editorial agents and image direction

Each edition moves through an evidence analyst, story editor, image director,
dual-provider search broker, image-to-story metadata proofreader, deferred
vision reviewer, and release auditor. The LLM writes search direction but never
receives either image API key; deterministic adapters call Pexels and Pixabay.
Both providers are searched for the strongest fit rather than alternated by
schedule.

Selected images are downloaded, cropped to a stable social-card ratio, and
served from `public/images/editions/`. Attribution remains attached in front
matter and every public placement. Search results are cached for 24 hours in
`.state/image-search-cache.json`, and `.state/image-ledger.json` prevents reuse.

Every handoff is recorded under `.state/editions/YYYY-MM-DD/` as sources,
evidence, drafts, image briefs, candidates, visual reviews, failed-draft
diagnostics, and a release manifest. DeepSeek performs metadata alignment today. The pixel-level
`VisionReviewer` interface deliberately reports `pending` until an image-capable
model is connected, so the system never mistakes tags for vision.

## Publisher surfaces

The Astro build generates a standard full-content RSS feed at `/rss.xml`, a
normal sitemap index, a two-day Google News sitemap, and `robots.txt`. All four
use the same draft gate as the public article routes. Affiliate placements are
removed from RSS content while source attribution and article health notes are
preserved.

Published article pages include a visible byline and publication time,
`NewsArticle` structured data, canonical metadata, and links to the original
reporting. About, editorial policy, affiliate disclosure, privacy, and contact
pages provide the publication identity expected by readers and distribution
partners.

## Daily edition

Each run selects three unprocessed stories. The highest-ranked story becomes a
source-enriched 600–900 word **Deep Read**; the next two become compact
**Signals**. Lead selection scans a wider candidate pool and promotes the
highest-ranked story whose source page provides enough material. Summary-only
stories remain Signals rather than being padded. Only the Deep Read receives a
contextual affiliate slot. Invalid model output receives a validation-specific
repair pass. A useful 350–499 word repaired lead can remain a focused draft for
human review; a lead that still fails is retried as a Signal. Story failures are
recorded and isolated so the rest of the edition continues. The checked-in workflow runs once each morning at
11:17 UTC and can also be run manually.

## Feed portfolio

The default `config/feed-portfolio.json` blends NIH, FDA, and MedlinePlus
authority with Medical Xpress healthy-aging, nutrition, sleep, and neurology
discovery feeds. The engine deduplicates stories, scores them for older-reader
relevance, and drafts only the strongest items across the entire pool. A soft
per-publisher cap keeps any one outlet from dominating when several publishers
have fresh material. Feed failures are isolated so one unavailable source does
not stop the batch. Sources marked `preserve` keep their supplied headline and
link unchanged.

Set `RSS_FEEDS_JSON` only when you need to override the checked-in portfolio.

### Potential signal watchlist

`config/potential-signal-feeds.json` keeps prospective sources separate from
the production portfolio. The current comparison set uses the two active
ScienceDaily feeds as its baseline and observes WorldwideHealth, The Guardian's
Alternative Medicine feed, and Alternative Medicine Magazine without allowing
them into ranking, drafting, or publication yet.

## GitHub Actions

Add `DEEPSEEK_API_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`, and optionally
`AFFILIATE_OFFERS_JSON` as repository secrets. The checked-in feed portfolio works without an `RSS_FEED_URL` secret;
`RSS_FEEDS_JSON` can override it. The workflow runs daily and commits new
drafts. Its commit step also preserves diagnostics when every story fails, while
the generation step remains visibly failed in GitHub Actions.

Generated editions remain drafts until the release manifest records completed
image and human editorial review.

## Trend radar

The scheduled workflow also writes `.state/trend-radar.json`. It queries
topic-seeded Google News RSS searches, clusters similar headlines, scores
mention count, source diversity, and freshness, and records a recommendation
for editorial review. This is a discovery aid, not an automatic publishing
feed: a human still verifies the topic against an authoritative source and
decides whether it deserves an Agewell article.
