# Topic-Agnostic Publishing Workflow

This is the reusable operating manual for the Agewell Brief engine. It records
the system we built and the decisions made during deployment. To reuse it for
another publication, replace the identity, source portfolio, categories,
editorial register, images, and commercial configuration; keep the orchestration,
audits, and release gates.

## 1. What the system does

```text
RSS / Atom sources + trend radar
            ↓
source normalization, sanitation, deduplication
            ↓
Assignment Editor selects the edition lineup
            ↓
evidence analyst → story writer → copy editor
            ↓
image director → Pexels/Pixabay search → metadata proofreader
            ↓
commercial integrity → release manager
            ↓
Markdown + audit bundle
            ↓
Astro build → Cloudflare deployment → RSS / sitemaps / search discovery
            ↓
Cloudflare reader trends → social packages → MoneyPrinterTurbo handoff
```

The pipeline is an editorial desk with deterministic safeguards around the
language models. The models assist with selection, synthesis, and presentation;
they do not replace source links, evidence boundaries, attribution, or release
audits.

Current production components:

- Python orchestration in `agewell/`.
- Astro frontend in `src/`.
- Feed and trend configuration in `config/`.
- Scheduled GitHub Actions in `.github/workflows/aggregate.yml`.
- Static deployment through Cloudflare Workers Builds.
- Social distribution through Upload-Post, with trend-ranked packages and
  publishing still gated behind review.
- Public site: `https://agewellbrief.com`.
- Repository: `https://github.com/elura172/agewell-brief`.

## 2. Repository and environment setup

Use a private GitHub repository for source code, configuration, generated
content, and audit artifacts. Keep secrets out of Git, Markdown, prompts,
screenshots, and state files.

Local setup:

```bash
cd /Users/mirrr/agewell-brief
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
```

Required runtime configuration is supplied as local environment variables or
GitHub Actions secrets. The current workflow uses:

- `DEEPSEEK_API_KEY` and `LLM_BASE_URL`/`LLM_MODEL` for generation.
- `RSS_FEED_URL` or `RSS_FEEDS_JSON` for the feed portfolio.
- `AFFILIATE_OFFERS_JSON` for reviewed commercial links.
- `PEXELS_API_KEY` and `PIXABAY_API_KEY` for image search.
- Optional publishing controls: `AUTO_PUBLISH`, `AUTO_PUBLISH_UNTIL`,
  `MAX_ITEMS`, and `MAX_ITEMS_PER_PUBLISHER`.

Never paste actual API keys into this document. Rotate a key immediately if it
appears in shell history, a commit, a log, or a chat transcript.

## 3. Source portfolio

Maintain real RSS or Atom URLs in `config/feed-portfolio.json`; a website
homepage is not a feed. Each source records its publisher, authority class,
priority, categories, headline mode, daily cap, and whether a secondary check is
required.

Use a balanced portfolio:

- primary research and public-health sources for factual grounding;
- specialist science and medicine publications for discovery and variety;
- consumer-safety and regulatory sources for practical alerts;
- carefully selected general-interest or alternative-health sources for
  reader relevance, with claims checked against stronger sources where needed.

The active portfolio includes NIH, FDA, MedlinePlus, Medical Xpress,
ScienceDaily, The Guardian's alternative-medicine feed, and Alternative
Medicine Magazine. WorldwideHealth remains in
`config/potential-signal-feeds.json` until it proves useful and reliable.

The ingestion layer:

1. fetches RSS and Atom documents with a clear user agent;
2. sanitizes malformed entities and hostile or irrelevant markup;
3. normalizes titles, links, publishers, dates, and summaries;
4. extracts source pages when permitted and useful;
5. deduplicates by normalized URL/title and SHA-256 article ID;
6. applies publisher and category caps;
7. records failures rather than silently dropping them.

Source variety is not a substitute for evidence. A discovery source can inspire
a brief, while the final wording must stay within the source material and any
available corroboration.

## 4. Trend-led selection

`config/trend-seeds.json` defines durable topic families such as healthy aging,
sleep, circadian health, brain health, mobility, metabolic health, consumer
safety, and nutrition. `scripts/trend_radar.py` queries Google News RSS for
those seeds, scores freshness and relevance, and writes trend artifacts under
`.state/trends/`.

Strong radar topics become real `FeedItem` candidates. The pipeline therefore
does not merely rank stories already in the RSS portfolio; it can discover a
timely angle and then seek source material for it.

Selection should optimize for a useful mix, not raw volume:

- timely signals with a clear reader reason to care;
- evergreen context that explains recurring themes;
- source and category diversity;
- enough evidence for the intended article length;
- no duplicate angle or repetitive headline pattern.

Run the radar manually when calibrating a new topic:

```bash
python3 -m scripts.trend_radar
```

Treat trend scores as editorial leads, not proof of medical importance or search
demand. Verify every selected item against the linked source.

### Reader-trend ranking

`scripts/cloudflare_trending.py` queries Cloudflare GraphQL Analytics for the
most visited `/brief/.../` paths and writes `src/data/trending.json`. The current
zone permits a one-day query window, so the ranking is refreshed daily rather
than presented as a misleading seven-day total. Only published article slugs
are admitted to the manifest.

The standalone `.github/workflows/trending.yml` job refreshes the ranking,
packages the selected articles for social distribution, synchronizes the
persistent manifest, and commits the resulting state. This keeps trend
measurement independent from a slow or failed LLM generation run.

## 5. Editorial desk and subagents

Each subagent has a narrow contract and receives only the material needed for
its task. Deterministic fallbacks keep the pipeline usable when an API fails.

### Assignment Editor

Chooses the day's lineup from normalized feed and trend candidates. It assigns
lead, signal, or context roles and proposes an angle. It must preserve source
diversity and avoid selecting several versions of the same story.

### Evidence Analyst

Extracts study type, population, intervention or exposure, outcome, numbers,
limitations, confidence, and unsupported claims. It must not invent statistics,
causation, institutions, quotations, or treatment advice.

### Story Writer

Creates structured content: headline, dek, introduction, sections, three
takeaways, source context, and caveat. The factual boundary is the source page
and evidence packet. The register is clear, spirited, respectful, concrete,
and human; it is not a rigid “Boomer psychology” template.

### Copy Editor

Improves clarity, rhythm, specificity, and readability without changing factual
fields. It restores required structure if a model omits it and rejects
unsupported escalation, miracle language, or manufactured urgency.

### Image Director

Turns the story into a visual brief containing subject, setting, mood,
composition, search queries, and an avoid-list. Prefer editorially relevant,
authentic imagery over product shots, fear imagery, stereotypes, and generic
medical drama.

### Image Broker and Metadata Proofreader

Search Pexels and Pixabay, avoid repeated images and creators, download only the
selected asset, and preserve provider/photographer attribution. The metadata
review checks whether title, tags, dimensions, and provider information fit the
brief. It is not pixel-level vision. A future vision reviewer may add a true
visual gate, but the system must never claim that review occurred when it did
not.

### Commercial Integrity Agent

Checks that offers are category-relevant, disclosed, reachable, and within the
maximum link count. It prevents an attractive payout from overriding editorial
fit.

### Release Manager

Runs the final audit and writes a release manifest. It checks source HTTPS,
headline/dek presence, exactly three takeaways, required metadata, affiliate
limits, and unresolved failures. Automatic publishing can waive a human or
visual review requirement only when explicitly configured; deterministic safety
checks still apply.

## 6. Evergreen context layer

Local books, transcripts, and other licensed or authorized material may provide
background context. They are not silently treated as current evidence.

For each context library:

1. record provenance and authorization;
2. keep the raw library outside the repository;
3. extract only the passages needed for background;
4. label context separately from current reporting;
5. never attribute a current claim to a book or transcript unless it actually
   supports that claim.

Topic-specific projects and private intellectual material remain outside the
Agewell pipeline unless deliberately imported as a separate, documented
context source.

## 7. Article and image output contract

Each article is a Markdown file under `content/posts/` with frontmatter for:

- title, date, category, type, and `draft` status;
- original source URL, title, and publisher;
- article ID, edition ID, and rank;
- image URL/path, provider, creator, dimensions, source URL, and review state;
- affiliate disclosure and any release metadata.

Each run writes an audit bundle under `.state/editions/`, including candidates,
sources, evidence, drafts, image briefs, visual reviews, failures, context
metadata, and a release manifest. `.state/processed.json` tracks processed
article hashes so repeated runs do not create duplicates.

The public page adds original-source attribution, category navigation, related
published briefs, and an accessible reading layout. Content should be useful on
its own; affiliate placement must not obscure the reporting.

## 8. Affiliate and commercial routing

Reviewed ClickBank HopLinks are supplied through the
`AFFILIATE_OFFERS_JSON` secret and routed by category. The configuration can
contain multiple offers per category; the selector chooses up to three stable,
relevant offers for an article and adds tracking identifiers where supported.

The process is:

1. manually select and approve a real offer;
2. record its category and destination in the secret;
3. run `python3 -m scripts.check_affiliate_offers`;
4. confirm the link is technically reachable and manually verify the offer;
5. render two or three naturally placed links only when relevant;
6. place a clear affiliate disclosure near the recommendation.

An HTTP success response does not prove vendor approval, product quality,
attribution, or legal compliance. Do not invent vendor IDs or generate links to
products that have not been reviewed. Never use a sensational health claim as a
commercial pretext.

## 9. SEO and discovery layer

The Astro site provides:

- `/rss.xml` for syndication;
- `/sitemap-index.xml` for ordinary crawling;
- `/news-sitemap.xml` for recent news content;
- `/robots.txt` advertising the sitemap index;
- a public IndexNow key file at the site root for change notifications;
- `Article`/`NewsArticle` structured data with source, dates, image, topic, and
  keyword context;
- category topic hubs under `/topics/[slug]`;
- related-brief links and topic navigation on article pages.

The legitimate growth loop is: publish original synthesis with clear source
links, make it readable and technically crawlable, submit sitemaps, distribute
through permitted channels, and use Search Console/Bing data to improve topic
selection. Avoid doorway pages, keyword stuffing, copied source text, fabricated
authority, cloaked affiliate links, and scaled low-value articles. No SEO tactic
guarantees placement in Search, Discover, or news aggregators.

After deployment:

1. verify the domain in Google Search Console;
2. submit `/sitemap-index.xml`;
3. inspect the news sitemap and representative URLs;
4. add the property to Bing Webmaster Tools;
5. monitor impressions, queries, indexing, referrals, and errors for several
   days before changing the editorial mix.

IndexNow is wired into the publishing workflow. After a run commits changed
article files, `scripts/submit_indexnow.py` submits their public `/brief/.../`
URLs to the IndexNow endpoint. The key file is deliberately public and proves
domain ownership; it is not an API secret. Submission improves discovery
timeliness but does not guarantee crawling or indexing.

## 10. Scheduled publishing and deployment

The workflow in `.github/workflows/aggregate.yml` currently runs three times a
day at 13:00, 18:00, and 23:00 UTC. That corresponds approximately to 9am,
2pm, and 7pm Toronto time during daylight saving; UTC timings should be
rechecked when local scheduling matters.

Each run:

1. checks out `main`;
2. installs Python dependencies;
3. checks configured affiliate links;
4. builds the trend radar;
5. runs the Assignment Editor and editorial chain;
6. searches and reviews images;
7. runs commercial and release audits;
8. writes Markdown, images, state, and audit artifacts;
9. commits generated changes back to `main`.

The current first-week setting is:

```text
AUTO_PUBLISH=true
AUTO_PUBLISH_UNTIL=2026-08-09
MAX_ITEMS=1
```

This means the automated window is time-boxed through August 8, after which
new material returns to `draft: true` unless the cutoff is intentionally
extended. Change the cutoff only after reviewing the first-week evidence. A
manual `workflow_dispatch` run is the preferred way to test configuration.

Cloudflare Workers Builds watches the GitHub repository and rebuilds the Astro
site after generated commits. If a build fails, inspect the Cloudflare build
log first; a successful GitHub commit does not by itself prove that the public
deployment succeeded.

## 11. Social distribution

Upload-Post is connected to the publication's Facebook, TikTok, and YouTube
accounts. The current system automates the preparation and tracking layers; it
does not yet publish new posts automatically.

The live flow is:

```text
Cloudflare reader ranking
          ↓
scripts/social_package.py --trending
          ↓
Facebook / TikTok / YouTube copy + MoneyPrinterTurbo job
          ↓
scripts/social_manifest.py sync
          ↓
review → render → optional Upload-Post submission
```

The trend-aware package generator reads `src/data/trending.json`, selects the
top five published briefs, and writes `.state/social/trending.json`. Each
package preserves its trend rank and reader-visit count, includes the canonical
article URL, and creates a `ready_for_mpt` video job with the configured Jenny
voice and high-contrast caption settings.

The formats are deliberately platform-aware:

- Facebook receives a concise link-post caption and canonical Agewell URL. The
  caption is generated automatically, but the post is not submitted to
  Facebook by the trend workflow yet.
- TikTok receives a hook, short script, caption, and link-in-bio URL; it still
  requires a vertical video asset.
- YouTube receives a short-form title and description; it also requires a video
  asset.

Keep the article URL canonical and do not place affiliate links directly in
social captions. Review the generated package before enabling live publishing.
Upload-Post's current API supports text, photo, and video endpoints, but the
connected platforms do not all accept the same media type. The API key remains
in the `UPLOAD_POST_API_KEY` GitHub secret.

Every released article also receives a persistent record under
`.state/content-records/`, a MoneyPrinterTurbo handoff under
`.state/video-jobs/`, and platform state in `.state/social/manifest.json`.
Upload-Post request and job IDs are registered there, then reconciled by
`.github/workflows/social-status.yml` every 15 minutes. The monitor records
completed URLs, failures, and retry context without creating duplicate jobs.

Register a job after an Upload-Post submission with:

```bash
python3 -m scripts.social_manifest register \
  --article-id ARTICLE_ID \
  --platform youtube \
  --request-id REQUEST_ID \
  --job-id JOB_ID
```

The local content-factory runner consumes `ready_for_mpt` jobs from the
manifest, invokes MoneyPrinterTurbo with the configured English voice and
high-contrast captions, submits the resulting video to Upload-Post, and pushes
only state changes back to GitHub. `ops/com.elura.agewell-content-factory.plist`
provides a macOS LaunchAgent schedule at 15-minute intervals; a lock prevents
overlapping renders. The runner defaults to one article per pass so a slow
video job cannot flood the connected accounts.

Current automation boundary:

- Automated: trend selection, Facebook copy, TikTok copy, YouTube copy,
  canonical links, MoneyPrinterTurbo job creation, manifest synchronization,
  and Upload-Post status reconciliation.
- Review-gated: final script/video QA and new Upload-Post submissions.
- Not automated: direct Facebook publishing from the trend refresh workflow.

When live publishing is enabled, keep the same review gate for the first batch
and confirm that the manifest records a request ID and resulting post URL for
each platform.

## 12. Review, rollback, and incident handling

For a controlled release:

```bash
python3 -m pytest -q
npm run build
git diff --check
```

Inspect the latest `.state/editions/<date>/.../release-manifest.json` before
publishing. If an article is wrong, set its frontmatter back to `draft: true`
or remove it through a normal reviewed commit, then redeploy. Preserve the
audit artifact explaining the correction; do not rewrite history to hide it.

If a feed breaks, disable or hold that source in configuration and retain the
failure record. If an affiliate destination changes, remove it from the secret,
rerun the health check, and regenerate affected drafts. If a model or provider
fails, deterministic fallback content may keep the run alive, but the result
should remain a draft until reviewed.

## 13. Measurement and first-week calibration

Track the system as an editorial product, not only as an ad funnel:

- feed health and extraction failures;
- trend topics selected versus rejected;
- source and category diversity;
- evidence completeness and editor fallbacks;
- article impressions, clicks, referrals, and reading behavior;
- daily reader-trend rankings and social package performance by article;
- image reuse and attribution issues;
- affiliate clicks and conversions where available;
- release failures and Cloudflare build health.

Use at least a week of comparable editions before changing the cadence. Adjust
source weights, topic seeds, headline patterns, image queries, and edition times
from observed evidence. Do not optimize from one viral article, a single payout
claim, or a search result snapshot.

## 14. Reproduction template for another publication

1. Copy the repository and change publication identity, domain, logo, and
   design tokens.
2. Define the topic taxonomy and editorial register.
3. Add a diverse list of real RSS/Atom feeds and hold questionable sources in a
   potential-signal list.
4. Define durable trend seeds and run the radar manually.
5. Tune evidence, writing, copy, image, commercial, and release contracts.
6. Configure image providers and preserve attribution.
7. Add reviewed commercial offers, or run without monetization initially.
8. Run a dry edition and inspect every audit artifact.
9. Build the Astro site and verify RSS, robots, sitemap, schema, and mobile
   readability.
10. Deploy to the chosen static host and verify representative live URLs.
11. Publish a small reviewed batch.
12. Enable a short, explicit auto-publish window only after the audits pass.
13. Measure, curate, and extend automation deliberately.

The reusable pattern is therefore:

```text
discover → normalize → select → substantiate → write → edit → illustrate
→ audit → publish → measure → curate
```

The topic changes. The evidence boundary, provenance, disclosure, accessibility,
and release discipline do not.
