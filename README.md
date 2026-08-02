# Agewell Brief

Standalone RSS-to-editorial-draft pipeline for a readable health and longevity digest.

The first version intentionally produces Markdown drafts for review. It uses RSS metadata and summaries, links back to the original source, and writes structured output suitable for Hugo or Astro.

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY="..."
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
longevity article unless that category has its own reviewed HopLink.

Generated files land in `content/posts/`; processing state is stored in `.state/processed.json`.

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
contextual affiliate slot. The checked-in workflow runs once each morning at
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

## GitHub Actions

Add `DEEPSEEK_API_KEY` and optionally `AFFILIATE_OFFERS_JSON` as repository
secrets. The checked-in feed portfolio works without an `RSS_FEED_URL` secret;
`RSS_FEEDS_JSON` can override it. The workflow runs daily and commits new
drafts.

All generated articles should be reviewed before production publication, especially health, financial, and supplement claims.
