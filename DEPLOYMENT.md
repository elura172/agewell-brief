# Agewell Brief deployment checklist

## Already complete

- Python pipeline and tests
- Astro static frontend
- GitHub Actions workflow
- Draft-first publishing mode
- Persistent feed-item state committed to the repository

## Before the first cloud run

1. Replace `https://example.com` in `astro.config.mjs` with the production domain.
2. Add the actual RSS or Atom feed URL as `RSS_FEED_URL`. A publisher homepage is not a feed.
3. Add `OPENAI_API_KEY` as a GitHub Actions secret.
4. Add `AFFILIATE_OFFERS_JSON` only after each encrypted ClickBank HopLink has
   been created, decoded, and tested in Affiliate Link Tools. The pipeline adds
   article-level `tid` parameters automatically.
5. Push the repository to GitHub and run **Aggregate health briefs** manually.

## Review loop

Generated files are intentionally written with `draft: true`. Review the source, headline, claims, links, and commercial disclosure before changing a post to `draft: false`.

## Hosting

For Astro, use:

```text
Build command: npm run build
Output directory: dist
```

The hosting provider can rebuild after the Actions workflow commits a reviewed or newly published post.

## Finance and tax

Keep payment onboarding separate from the code deployment. Confirm entity classification, treaty eligibility, withholding, GST/HST treatment, and payout-account compatibility with the relevant provider and a Canadian cross-border tax professional.
