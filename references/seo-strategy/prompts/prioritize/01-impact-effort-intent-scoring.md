# Prioritize · Score every candidate by impact x effort x intent

**Loop stage:** Prioritize — rank the backlog on the evidence the first three stages produced.
**When to run:** once Diagnose defects and Cluster opportunities both exist.

Prioritize is where evidence becomes a decision. It is a reasoning stage — no new fetch —
that scores every candidate task from the artifacts already on the table, so sequencing
is defensible rather than intuitive.

## Evidence to gather (from prior stages, all free Tier-2)

- **Impact** — from Diagnose: the `audit_aggregate.py` weakest-category signal and each
  defect's severity; from Cluster: SERP centrality (a pillar outranks a lone spoke) and
  the money/authority tag.
- **Effort** — from Diagnose: whether a fix is a config change or a rebuild; from Cluster:
  new page vs. improve-existing; from Baseline: the real page-type mix and site depth.
- **Intent** — from Cluster's intent classifier: transactional/commercial nodes weigh
  toward near-term revenue; informational nodes weigh toward compounding authority.
- **Governing tilt** — from Baseline: the `business_type.py` vertical template adjusts the
  weights (a local business weights GBP/location work up; a publisher weights cluster
  breadth up).

`needs_tier1`: absolute opportunity size (volume x CPC) stays a never-fabricate field —
score with the free proxies (SERP centrality, intent, severity) and mark where a
connector would sharpen the ranking under `needs_tier1`.

## The prompt

> Score the candidate backlog for {domain}. For each candidate — every blocking technical
> defect, every citability fix, and every cluster node — assign an impact, effort, and
> intent rating using only the Baseline/Diagnose/Cluster evidence, and compute a combined
> priority. Apply the governing vertical template's weight tilt and state it. Rank the
> backlog and show the top items with the one-line evidence that justifies each rank. Do
> not use invented volume as an impact input; where a connector would change the order,
> note it under `needs_tier1`.

## Decision it drives

- **The ranked backlog** — a defensible order over defects and content nodes together.

## Hand off to

- `prioritize/02-sequence-the-roadmap.md` — turn the ranking into a dated, dependency-aware
  roadmap.
