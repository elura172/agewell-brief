# Agewell Brief

Standalone RSS-to-editorial-draft pipeline for a readable health and longevity digest.

The first version intentionally produces Markdown drafts for review. It uses RSS metadata and summaries, links back to the original source, and writes structured output suitable for Hugo or Astro.

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="..."
export RSS_FEED_URL="https://example.com/feed.xml"
python -m agewell.pipeline
```

Optional affiliate configuration is supplied as JSON:

```bash
export AFFILIATE_OFFERS_JSON='{"mobility":"https://example.com/offer?subid=agewell-mobility"}'
```

Generated files land in `content/posts/`; processing state is stored in `.state/processed.json`.

## GitHub Actions

Add `OPENAI_API_KEY`, `RSS_FEED_URL`, and optionally `AFFILIATE_OFFERS_JSON` as repository secrets. The workflow runs every six hours and commits new drafts.

All generated articles should be reviewed before production publication, especially health, financial, and supplement claims.
