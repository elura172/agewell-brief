# Agewell Brief deployment checklist

## Already complete

- Python pipeline and tests
- Astro static frontend
- GitHub Actions workflow
- Manual editorial preview mode
- Persistent feed-item state committed to the repository
- Daily Lead + Signals edition structure
- Cloudflare Worker deployment at `agewell-brief.elura172.workers.dev`
- Production custom domain at `https://agewellbrief.com`
- RSS, standard sitemap, news sitemap, robots, and publisher trust pages

## Before the first cloud run

1. Production domain configured as `https://agewellbrief.com`.
2. Add the actual RSS or Atom feed URL as `RSS_FEED_URL`. A publisher homepage is not a feed.
3. Add `DEEPSEEK_API_KEY` as a GitHub Actions secret. The default model is
   `deepseek-v4-flash`; set `LLM_MODEL=deepseek-v4-pro` when higher-cost editorial
   passes are useful.
4. Add `PEXELS_API_KEY` and `PIXABAY_API_KEY` as GitHub Actions secrets. The
   broker searches both libraries, downloads only the selected image, and keeps
   provider, photographer, and source attribution attached to the draft.
5. Rotate any image key that has appeared in chat, logs, or screenshots before
   enabling unattended runs.
6. Add `AFFILIATE_OFFERS_JSON` only after each encrypted ClickBank HopLink has
   been created, decoded, and tested in Affiliate Link Tools. The pipeline adds
   article-level `tid` parameters automatically.
7. Run **Aggregate health briefs** in its default `preview` mode and review the
   generated artifact before choosing any publishing path.

The optional evergreen context layer is local-only by default. Do not commit
the transcript library. A cloud run needs a separately authorized private
bundle or companion repository; otherwise the pipeline safely runs without
that background layer.

## Review loop

Manual preview runs generate files with `draft: true` and upload the changed
articles, images, and audit trail as a short-lived artifact. Review the source,
headline, claims, links, and commercial disclosure before selecting a publishing
mode. Scheduled runs retain their configured unattended-release behavior.

Each run also writes an audit trail to `.state/editions/YYYY-MM-DD/`. Review
`release-manifest.json` first: it names every incomplete source, editorial,
metadata, and visual gate without publishing automatically.

If a model response cannot be repaired, inspect `failed-drafts.json`. It retains
the validation error and raw attempts for editorial diagnosis. One failed story
does not stop the remaining edition, and failed items are not marked processed.

## Hosting

The private GitHub repository is connected to Cloudflare Workers Builds. The
Astro project remains a static build; Cloudflare publishes the generated
`dist/` assets and redeploys on pushes to `main`.

```text
Production branch: main
Deploy command: npx wrangler deploy
Static asset directory: dist
```

If GitHub Actions or Workers Builds is unavailable, the same production Worker
can be deployed directly after a local build:

```bash
npm run build
npx wrangler deploy
```

The checked-in `wrangler.jsonc` keeps the Worker name, compatibility date, and
static asset directory explicit so this fallback does not depend on dashboard
configuration.

Cloudflare's automatic Astro setup requires `public/.assetsignore`; Astro copies
it to `dist/` so Worker output files are not uploaded as public assets. The
custom domain is attached under **Settings → Domains & Routes**.

## Publisher discovery

- `https://agewellbrief.com/rss.xml` contains only published briefs and removes
  affiliate placements from syndicated content.
- `https://agewellbrief.com/sitemap-index.xml` lists public site routes.
- `https://agewellbrief.com/news-sitemap.xml` lists published articles from the
  previous two days and may be empty between editions.
- `https://agewellbrief.com/robots.txt` advertises both sitemaps.

Draft entries are excluded from every production route and discovery file.

## Finance and tax

Keep payment onboarding separate from the code deployment. Confirm entity classification, treaty eligibility, withholding, GST/HST treatment, and payout-account compatibility with the relevant provider and a Canadian cross-border tax professional.
