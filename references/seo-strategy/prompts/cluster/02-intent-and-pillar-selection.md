# Cluster · Confirm intent, page type, and pillar roles

**Loop stage:** Cluster — turn raw clusters into a reviewed architecture with page types.
**When to run:** right after the territory map, before anything is prioritized.

Clustering is deterministic, but roles and intent deserve a human-checked pass. This
prompt confirms which node is the pillar, what page type each node wants, and which
clusters map to near-term money versus long-term authority.

## Evidence to gather (free Tier-2)

- `scripts/seo/serp_cluster.py` intent classifier — labels each keyword
  transactional / commercial / informational / navigational (most-specific-first) and
  selects the pillar by SERP centrality. The intent-to-page-type mapping and the
  mixed-intent split rule are documented in `references/seo-cluster/hub-and-spoke.md`.

`needs_tier1`: commercial value per cluster (volume x CPC) is a never-fabricate field —
rank clusters by intent and SERP centrality on the free path; list the monetary sizing
under `needs_tier1`.

## The prompt

> Review the clustered architecture for {theme}. For each cluster, confirm the pillar is
> the genuinely SERP-central head term (override only with a stated reason), and assign a
> page type per node from its intent: informational -> guide/explainer/FAQ; commercial ->
> comparison/roundup/review; transactional -> product/pricing/service/booking;
> navigational -> usually not a content target. Split any cluster whose spoke intent
> diverges from the pillar. Tag each cluster **money** (transactional/commercial) or
> **authority** (informational) so Prioritize can balance near-term ROI against
> topical-authority building. Do not attach invented volume; size clusters under
> `needs_tier1`.

## Decision it drives

- **Page type per node** and **pillar confirmation** — what actually gets built.
- **The money-vs-authority balance** of the opportunity set, which shapes sequencing.

## Hand off to

- `prioritize/01-impact-effort-intent-scoring.md` — the money/authority tag is the intent
  axis of the score.
- `produce/01-brief-the-priority.md` — page type + pillar/spoke role are brief inputs.
