# Getting Agewell Brief into ChatGPT / OpenAI search

Researched 2026-08-06. Confidence is marked throughout:
**[documented]** = stated by OpenAI · **[reported]** = credible third-party, unconfirmed ·
**[folklore]** = commonly repeated, not supported by evidence.

## The short version

There is **no submission mechanism for editorial content**. No publisher portal, no feed,
no sitemap ping, no ChatGPT equivalent of Search Console. It is purely passive crawling.
**[documented, by absence across OpenAI's own docs]**

The only factor OpenAI actually documents is whether you let `OAI-SearchBot` crawl you.
Agewell Brief already does, and that was verified at the CDN as well as in robots.txt —
which matters, because Cloudflare's AI-bot blocking silently deletes ChatGPT visibility
regardless of robots.txt. We are clean on both.

So the honest answer is that the technical work was already done, and the binding
constraint is age and external links, not configuration.

## OpenAI's crawlers

Four bots, independently controllable via robots.txt tokens. **[documented]**
https://developers.openai.com/api/docs/bots

| Token | Controls |
|---|---|
| `OAI-SearchBot` | **Appearing in ChatGPT search.** This is the one that matters. |
| `GPTBot` | Training data collection. Blocking it does *not* remove you from search. |
| `ChatGPT-User` | User-triggered fetches; not automated crawling. |
| `OAI-AdsBot` | Safety validation for pages submitted as ChatGPT ads. |

Verification is UA token **plus** source IP within OpenAI's published ranges, so spoofed
user agents don't get in. Note the supported configuration "visible in search, not used
for training" = `Allow: OAI-SearchBot` + `Disallow: GPTBot`. We currently allow both by
falling under `User-agent: *`. That is a deliberate decision worth making, not a default
to drift into.

## "The OpenAI shelf"

No OpenAI product, program, or feature by that name exists. The phrase is e-commerce
analyst jargon ("the AI shelf" / "the agentic shelf") for the set of products an AI
assistant considers and surfaces. It describes a market position, not something you sign
up for. **[folklore as a product name]**

The real thing underneath it is the **OpenAI Product Feed / Agentic Commerce Protocol** —
and that *does* have a genuine submission route, gated by application at
https://chatgpt.com/merchants. It is a flat-file product feed (Google Shopping-compatible
profile accepted) with required `is_eligible_search` / `is_eligible_checkout` flags,
GTIN/MPN identifiers, SFTP or API delivery. **[documented]**
https://developers.openai.com/commerce/specs/feed

**This almost certainly does not apply to Agewell Brief.** It is for merchants selling
products with identifiers and checkout. Agewell Brief is a publisher whose commercial
layer is affiliate links (ClickBank HopLinks, Fullscript plans) and free PDF field
guides — no owned SKUs, no GTINs, no checkout. Applying would be a category error unless
the business later sells its own products directly.

## What actually influences citation

OpenAI publishes **no ranking factors** for ChatGPT search. Everything below is inference.

- **`OAI-SearchBot` access** — the only documented factor, and it is binary. ✅ done.
- **Bing indexation** — ChatGPT search names Bing as a third-party provider. Worth keeping
  healthy as a hedge; it is neither sufficient nor provably necessary. Bing Webmaster
  Tools is the *only* index telemetry obtainable, since OpenAI offers none. **[reported]**
- **Structured data** — contested. An Ahrefs study of 1,885 pages found no meaningful
  citation lift (~+2.2%, statistical noise) for editorial content. Vendor studies claiming
  +39% are correlational and mostly published by firms selling schema services. Schema is
  cheap, harmless, and helps parsers — but it should not be sold as a ChatGPT lever.
  **[contested, leaning folklore for non-commerce]**
- **IndexNow** — a Microsoft/Bing/Yandex protocol. **There is no OpenAI IndexNow
  endpoint.** It can only matter transitively via Bing. Useful for Bing freshness; calling
  it a "ChatGPT visibility" lever is **[folklore]**.
- **llms.txt** — **[folklore]**, and the most-conflated point in this space. OpenAI
  *publishes* an llms.txt for its own docs; that is OpenAI emitting the file for other
  agents, not evidence that OAI-SearchBot *reads* one on your site. No major provider has
  committed to consuming it in production retrieval. Not worth building on this evidence.
- **Content freshness** — **[reported]**, plausible given real-time retrieval design.
- **Licensing / publisher deals** — the unmeasurable elephant. OpenAI's named publisher
  partnerships plausibly outweigh any on-site markup. Unknowable from outside.

Also worth knowing: one large study found ChatGPT cites only ~15% of pages it *retrieves*.
Retrieval and citation are separate funnels and the second one cannot be instrumented.

## What we changed on 2026-08-06

- Topic pages now emit `CollectionPage` + `ItemList` + `FAQPage` schema; they previously
  had none while brief pages carried full `NewsArticle`. Framed as hygiene, not a lever.
- `headline_mode` flipped to `rewrite` on all 26 journal/preprint feeds. Raw academic
  titles ("Regional cerebral arterial elasticity is associated with cardiovascular health
  in cognitively healthy older adults") match no natural query; this is the most defensible
  retrieval improvement available, since retrieval is query-driven. New briefs only.
- Ran IndexNow (56 URLs, HTTP 200) — it had been stalled since 2026-08-04 with the pulse
  outage. Bing hedge, not a ChatGPT lever.

## What is actually blocking us

The domain is four days old (first commit 2026-08-02) and returns nothing for
`site:agewellbrief.com`. It is not yet in any index. No configuration change shortcuts
that. The real levers left are all off-site and human:

1. **Verify in Bing Webmaster Tools** — needs a login; the only visibility telemetry that exists.
2. **Backfill the 49 published briefs' headlines** — currently raw source titles.
3. **Earn external links.** Nothing here substitutes for being cited by other sites.
4. **Decide the GPTBot posture** — allow training or not.
