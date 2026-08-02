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

An offer assigned to `general wellness` acts as the evergreen fallback for any
category that does not yet have a dedicated offer.

Generated files land in `content/posts/`; processing state is stored in `.state/processed.json`.

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
`RSS_FEEDS_JSON` can override it. The workflow runs every six hours and commits
new drafts.

All generated articles should be reviewed before production publication, especially health, financial, and supplement claims.
