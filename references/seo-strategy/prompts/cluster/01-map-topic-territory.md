# Cluster · Map the winnable topic territory by SERP overlap

**Loop stage:** Cluster — turn a keyword universe into the content architecture to invest in.
**When to run:** after Diagnose, once the site's own state is measured; before Prioritize.

Diagnose measures *your* site; Cluster measures the *market*. This prompt groups keywords
by the only signal that predicts whether one URL can rank for a group — shared Google
results — and returns hub-and-spoke architecture, not a flat keyword list.

## Evidence to gather (free Tier-2)

- `scripts/seo/serp_cluster.py` — deterministic SERP-overlap clustering over an
  orchestrator-supplied SERP blob (`{keyword: [ranked urls]}`). It computes pairwise
  shared-top-N overlap, forms single-linkage components at a chosen threshold, picks the
  most SERP-central keyword as each pillar, classifies intent, and emits the internal-link
  matrix. It **never fetches** — SERP *acquisition* is a separate WebSearch (or connected
  DataForSEO/Semrush) step. See `references/seo-cluster/serp-overlap-method.md`.

`needs_tier1`: keyword search volume, CPC, and difficulty are never-fabricate fields —
the clusters ship complete without them, with those numbers listed under `needs_tier1`
until a DataForSEO/Semrush connector is present.

## The prompt

> Map the topic territory for {seed keywords / theme}. Expand the seeds into a keyword
> set, acquire each keyword's top results into a SERP blob (WebSearch on the free path;
> a connected SERP MCP for bulk), then cluster deterministically. Return one pillar plus
> its spokes per cluster, the intent label per keyword, and the internal-link matrix.
> Flag any cluster pulled together only through a single-linkage chain (a `bridged`
> member that does not co-rank with the pillar) and any mixed-intent cluster that should
> split. Present volume/CPC/difficulty as `needs_tier1`, never as invented numbers. State
> which tier acquired the SERPs.

## Decision it drives

- **The real content architecture** — the set of pillar pages and their spokes — that
  the plan will invest in (each node is a candidate task).
- **Which keywords do not deserve a page** (navigational singletons, un-clustered noise).

## Hand off to

- `cluster/02-intent-and-pillar-selection.md` — confirm roles and page types per node.
- `prioritize/01-impact-effort-intent-scoring.md` — each cluster becomes a scored opportunity.
