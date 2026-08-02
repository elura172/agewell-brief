# Topic-Agnostic Publishing Workflow

This document describes the reusable system behind Agewell Brief. Replace the
topic, source portfolio, editorial voice, and commercial offers to reproduce
the same engine for another publication.

## 1. System shape

```text
RSS / Atom feeds
      ↓
source selection and deduplication
      ↓
source-page extraction
      ↓
evidence analyst
      ↓
story editor
      ↓
image director → image search → metadata proofreader → optional vision review
      ↓
Markdown draft + audit artifacts
      ↓
human review
      ↓
static build → hosting → RSS / sitemap / social distribution
```

The system is intentionally modular. A new publication changes configuration
and editorial prompts, not the core orchestration pattern.

## 2. Content inputs

Maintain a feed portfolio in `config/feed-portfolio.json`. Each source should
have a name, a real RSS or Atom URL, a priority, and an optional publisher
group. Use several source types:

- authoritative or primary sources for factual grounding;
- specialist publications for discovery and variety;
- public-interest or consumer-safety sources for useful alerts;
- optional local or first-party material, clearly labeled as context rather
  than independent evidence.

The ingestion layer fetches feeds, supports RSS and Atom, sanitizes malformed
HTML entities, normalizes known URLs, deduplicates by normalized title, and
filters previously processed links using a SHA-256 article ID.

## 3. Selection and edition structure

The selector ranks stories using source priority, topic relevance, freshness,
and diversity. A publisher cap prevents one outlet from filling the edition.

The default edition contains:

- one source-enriched lead analysis;
- two short signals;
- one image per item when a suitable, attributed image is available.

The lead is promoted only when enough source-page material is available. A
summary-only item remains a short signal instead of being padded.

## 4. Editorial agent chain

Each agent has one job and receives only the material required for that job.

### Evidence analyst

Extracts study type, supported claims, limitations, confidence, and claims the
source does not justify. It must not invent numbers, institutions, causation,
or medical advice.

### Story editor

Produces structured JSON containing a headline, introduction, sections,
takeaways, and caveat. It uses the source material as the factual boundary and
the evidence packet as a guardrail.

The publication register should be clear, spirited, respectful, concrete, and
varied. Style guidance is preference, not a rigid template.

### Image director

Creates an editorial image brief: subject, setting, mood, composition,
avoid-list, and several search queries. It should favor authentic editorial
images over product shots, fear imagery, stereotypes, or generic medical
drama.

### Image broker

Searches configured providers such as Pexels and Pixabay, caches results,
avoids reused images and creators, downloads only the selected image, and
preserves provider and photographer attribution.

### Metadata proofreader

Checks whether the selected image actually fits the story brief using metadata.
This is not pixel-level vision. A future vision-capable reviewer may replace
the deferred visual gate, but the system must never claim visual review that
did not happen.

## 5. Output contract

Every generated article contains frontmatter for:

- title, date, draft status, category, and content type;
- original source URL, title, and publisher;
- image provider, creator, source URL, dimensions, and review status;
- edition ID and rank;
- optional affiliate disclosure.

Every run writes an audit bundle under `.state/editions/` containing sources,
evidence, drafts, image briefs, candidates, visual reviews, failures, context
metadata, and a release manifest.

Raw private libraries and source excerpts should not be committed to the
repository. Optional local context is provenance-preserving and background-only.

## 6. Commercial routing

Commercial offers are configured through the encrypted
`AFFILIATE_OFFERS_JSON` repository secret. Offers should be:

- explicitly approved before use;
- valid HTTPS HopLinks or equivalent tracked URLs;
- checked for technical reachability before generation;
- routed by exact editorial category;
- disclosed visibly near the recommendation.

The default policy places one contextual offer on the lead only. Signals do
not receive offers. Never attach an unrelated offer merely because it pays
more. Technical reachability is not proof of attribution, approval, quality, or
legal compliance; verify each offer manually with the provider.

## 7. Review gates

Generated material starts as `draft: true`. Before publishing, review:

1. source link and original headline;
2. study type, numbers, quotations, and limitations;
3. headline and claims for unsupported escalation;
4. affiliate relevance and disclosure;
5. image fit, crop, attribution, and metadata;
6. privacy, health, financial, and advertising requirements;
7. release manifest and failed-draft diagnostics.

Only after these checks should a human change the article to `draft: false`.

## 8. Deployment

The repository is built as a static Astro site and deployed by Cloudflare
Workers Builds. A push to `main` rebuilds the public site. The same pattern
works with another static host if its build command and output directory are
configured accordingly.

The scheduled GitHub Action:

1. checks out the repository;
2. installs Python requirements;
3. checks affiliate health;
4. runs the aggregation pipeline with repository secrets;
5. commits generated drafts, images, state, and audits.

The workflow can also be triggered manually for a controlled test edition.

## 9. Publisher discovery

Keep these public endpoints valid:

- `/rss.xml` for syndication;
- `/sitemap-index.xml` for ordinary crawling;
- `/news-sitemap.xml` for recent news content;
- `/robots.txt` advertising the sitemap index.

Verify ownership in Google Search Console, submit the sitemap index and child
sitemaps, import the property into Bing Webmaster Tools, and configure the
publication in the relevant news publisher tools. Indexing is not immediate;
measure impressions and clicks over several days before changing strategy.

## 10. Measurement loop

Run a consistent edition cadence for at least a week before optimizing. Track:

- impressions, clicks, and search queries;
- RSS and referral traffic;
- article-level engagement;
- lead versus signal performance;
- image and source performance;
- affiliate clicks and conversions where available.

Use observed response to refine source weights, topic mix, headline patterns,
edition timing, and distribution. Do not optimize from one article or from
advertiser payout claims alone.

## 11. Reproduction checklist

For a new topic:

1. copy the repository and replace publication identity and design;
2. define categories and classification rules;
3. build and test a diverse feed portfolio;
4. tune evidence and editorial prompts to the topic;
5. configure image providers and attribution handling;
6. add reviewed commercial offers, if any;
7. run a manual dry edition;
8. inspect the audit bundle and generated drafts;
9. deploy the static site;
10. verify RSS, robots, sitemaps, and ownership;
11. publish a small reviewed batch;
12. measure before scaling automation or distribution.

Secrets belong in local environment variables or repository secrets, never in
source files, audit artifacts, prompts, screenshots, or chat transcripts.
