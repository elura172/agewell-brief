# Agewell Brief deployment checklist

## Already complete

- Python pipeline and tests
- Astro static frontend
- GitHub Actions workflow
- Draft-first publishing mode
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
4. Add `AFFILIATE_OFFERS_JSON` only after each encrypted ClickBank HopLink has
   been created, decoded, and tested in Affiliate Link Tools. The pipeline adds
   article-level `tid` parameters automatically.
5. Push the repository to GitHub and run **Aggregate health briefs** manually.

## Review loop

Generated files are intentionally written with `draft: true`. Each edition
contains one 600–900 word Deep Read and two compact Signals. Review the source,
headline, claims, links, and commercial disclosure before changing a post to
`draft: false`.

## Hosting

The private GitHub repository is connected to Cloudflare Workers Builds. The
Astro project remains a static build; Cloudflare publishes the generated
`dist/` assets and redeploys on pushes to `main`.

```text
Production branch: main
Deploy command: npx wrangler deploy
Static asset directory: dist
```

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
