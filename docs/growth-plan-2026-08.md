# Agewell Brief → Program: next actions

Drafted 2026-08-06. Ordered by leverage, not by effort.

## First, checking the existing work

You asked me to verify rather than assume. Two things came back different from expected.

**Bing: registered is not the same as indexed.** `site:agewellbrief.com` returns zero
results in Bing right now. Registering in Webmaster Tools gives you the dashboard and
lets you submit; it does not put you in the index. Indexation follows crawling, and the
domain is four days old. Nothing is wrong — but the outcome hasn't happened yet, so any
plan that assumes Bing coverage is premature. Bing Webmaster Tools remains the only
index telemetry that exists anywhere (OpenAI publishes none), so it is still worth having.

**The Substack is currently working against the site, not for it.** This is the most
consequential finding and it inverts an assumption:

- Substack posts contain **zero** links back to agewellbrief.com. Not one.
- Each post is **self-canonical** to `agewellbrief.substack.com`.
- The bodies carry the same structure as the site briefs ("why this matters",
  "what was found").

So the same content exists twice: once on a four-day-old domain with no authority, and
once on Substack, which has enormous authority and claims the canonical. Search engines
will prefer the Substack copy, and the site earns no link credit for it. The one backlink
source you fully control is pointed the wrong way.

`scripts/substack_publisher.py` line 56 *does* compose a "Read full web edition" link, but
it is absent from all 23 published posts — those went out via a different path or an
older version. Publishing has also been stalled since 2026-08-04.

## P0 — Turn Substack from a competitor into a feeder

Highest leverage available, and it is a small change.

1. Set each Substack post's canonical URL to its agewellbrief.com brief. This consolidates
   ranking signals onto the site instead of splitting them.
2. Link back to the specific brief in the body, not just the homepage.
3. Wire `substack_publisher.py` into `run_daily_pulse.sh` so publishing resumes.

**Blocked on:** `SUBSTACK_SID` (or email/password) in `.env`. Nothing here works without it.

## P1 — A latent config regression

`config/affiliate-offers.json` currently routes **all six categories to one identical
hoplink**. The live site is fine — it has 10 distinct offers correctly varied by category,
baked in from an earlier build — but the next pipeline run using this config would collapse
them, silently undoing the category-matching the README describes as a safety feature.

Also: the six offers in that file are *named* after your own spiral frameworks ("Luminous
Brain Health Protocol", "Inner Ecology Microbiome Guide") while pointing at a third-party
ClickBank product (NeuroVera). Those names are not rendered anywhere today, so no reader
is currently misled. But if any future template surfaces `name`, a third-party product
starts wearing your framework's clothes. Rename them now, while it costs nothing.

## P2 — Your ChatGPT query method, made rigorous

Your instinct is right and it is the correct method. Two refinements make it evidence
rather than anecdote:

**The signal is which sources ChatGPT cites, not what it says.** The prose varies run to
run; the citation list tells you who currently owns that query and what shape of page
wins. Log the cited URLs, not the answer.

**One run is noise.** Retrieval is non-deterministic. Run each query several times across
days and count how often each domain appears.

Concretely:

1. Build a fixed query set from the six spirals — roughly 8–10 natural-language questions
   each, phrased the way a person actually asks ("why do my hands get cold when I fast",
   not "peripheral vasoconstriction metabolic"). Around 50–60 queries total.
2. Run them in ChatGPT with search on. Record: cited domains, cited page types, whether
   agewellbrief.com appears at all.
3. Analyse what the winners share — depth, structure, freshness, whether they answer the
   question in the first screen.
4. Shape our topic pages and framework pages to answer those questions directly and
   honestly. We are matching real questions with real answers, not gaming anything.

**The KPI is simple:** how many of the ~55 queries cite agewellbrief.com. Today it will be
zero, because we are not indexed. That zero is the baseline, and it is the honest starting
number.

This is manual work initially. Automate only after the query set has proven stable.

## P3 — Meshing the two program tiers

Right now the briefs carry two competing commercial paths: third-party ClickBank offers
and your own Fullscript program. Every ClickBank click is revenue that builds someone
else's asset, and two paths convert worse than one.

Recommendation: **make your own program the primary path everywhere and demote or drop
ClickBank.** Three reasons — it compounds into an asset you own, it removes the trust
liability of third-party health offers on a site whose whole positioning is
source-led rigour, and it gives readers one clear next step.

The tier structure then reads naturally:
- **Brief** → topical curiosity, source-linked, free.
- **Light tier** (Fullscript + PDF field guide) → the on-ramp, low commitment.
- **Full program** (dedicated site) → the destination for people who want the whole frame.

**Blocked on:** I don't know the dedicated program site's URL, so I can't plan the handoff,
check its trust signals, or cross-link the two properly. Send it and I'll audit it the way
I audited this one.

## P4 — Riding news spikes

The infrastructure for this already exists and now works again: `news-sitemap.xml` carries
the last two days, IndexNow fires on each pulse (56 URLs accepted today after being stalled
since Aug 4), and the pulse runs three times daily. The binding constraint is not tooling —
it is that spike-riding requires being in an index first. This becomes real after P0 and
Bing indexation land, not before.

## Done today

- Every commission-earning link now carries `rel="sponsored"` — 150 anchors (25 ClickBank,
  125 Fullscript) previously passed ranking signals through paid links, which is a link
  scheme and a direct trust cost on the pages we want cited. Editorial citations to
  journals stay followed. Guarded in three layers so it cannot recur.
- Topic pages emit `CollectionPage` + `ItemList` + `FAQPage` schema (they had none).
- `headline_mode` flipped to rewrite on all 26 journal/preprint feeds.

## What I need from you

1. `SUBSTACK_SID` in `.env` — unblocks P0, the highest-leverage item.
2. The dedicated program site URL — unblocks P3.
3. A decision on ClickBank: keep, demote, or drop.
