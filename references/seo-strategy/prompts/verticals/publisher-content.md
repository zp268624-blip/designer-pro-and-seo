# Vertical template · Publisher / content / media

**Covers `business_type.py` output:** `publisher` (Article/News/BlogPosting schema, high
article volume, editorial/subscribe/newsletter language, ad-supported signals).
**Center of gravity:** topical clusters at volume; freshness cadence; author E-E-A-T; the
authority layer *is* the product.

A strategic **tilt** applied over the six-stage loop.

## What wins here

A publisher's asset is topical authority earned across many interlinked articles. The
winnable territory is breadth plus depth — comprehensive coverage of a topic with a strong
internal-link graph — and the recurring failure modes are content decay (stale top pages),
orphaned articles, and thin author signals. Intent is mostly informational, so the play is
authority compounding, not near-term transaction.

## Per-stage tilt

- **Baseline** — the inventory is article-dominated and deep; `crawl_inventory.py` exposes
  orphans and over-deep articles. Expect high `page_types.blog` counts.
- **Diagnose** — weight **freshness/decay, internal-link health, and author E-E-A-T
  signals up** (byline, date, sourcing — see `references/shared/eeat-criteria.md`). GEO
  citability is high-value: publisher passages are prime AI-citation targets.
- **Cluster** — this is the vertical where clustering pays most: build large hub-and-spoke
  structures; the internal-link matrix is a first-class deliverable, not an afterthought.
- **Prioritize** — weight **cluster breadth and refresh-decay up**. Refreshing a decaying
  top performer often beats a net-new article for the same effort.
- **Produce** — schema is `Article`/`NewsArticle` with author/date; briefs enforce
  first-hand experience and sourcing; the link matrix wires each new spoke into its cluster.
- **Verify** — drift watches title/H1/word_count/schema across the cluster; the trend
  timeline (`drift_history.py`) is the compounding signal; traffic/impressions are `needs_tier1`.

## Scripts that matter most

`business_type.py` (confirm publisher) -> `serp_cluster.py` (large clusters + link matrix)
-> `geo_check.py` (passage citability) -> `drift_history.py` (decay/refresh trend).

## Money vs authority

For a publisher the two nearly merge: authority *is* the revenue engine (ads/subscriptions
follow traffic). Bias toward cluster breadth and refresh-decay; monetization is downstream
of topical authority.
