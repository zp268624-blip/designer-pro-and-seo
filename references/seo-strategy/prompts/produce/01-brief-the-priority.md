# Produce · Turn each priority into a build-ready brief

**Loop stage:** Produce — convert a roadmap item into a work order someone can build.
**When to run:** on each top-of-roadmap content item, in sequence.

A roadmap line ("build the pricing pillar") is not buildable until it is a brief. This
prompt hands each prioritized node to the plugin's brief engine so the writer or builder
gets structure, word counts anchored on real competitors, entities, links, and the
citability constraints Diagnose surfaced.

## Evidence to gather (free Tier-2)

- `seo-content-brief` (skill) — produces the per-section heading structure, per-section
  word-count guidance **anchored on the actual top-ranking pages** (not a generic
  minimum), required entities/sub-topics, internal/external links, and schema
  recommendations. Free path: analyze the competitor URLs you provide; DataForSEO
  auto-fetches the SERP when connected.
- The node's **role and intent** from Cluster (pillar vs. spoke; page type) and its
  **citability requirements** from `diagnose/02` are brief constraints, not afterthoughts.

`needs_tier1`: competitor traffic/authority is a never-fabricate field — brief against
the observed top-ranking pages; list competitor traffic estimates under `needs_tier1`.

## The prompt

> Brief {this roadmap node}. Pass its keyword, page type, and pillar/spoke role to the
> content-brief engine along with the top-ranking competitor URLs. Produce the H1 +
> heading outline, per-section word-count ranges anchored on those competitors, the
> entities every competitor covers plus the gap none cover (the differentiation angle),
> the internal links from the cluster's link matrix, and the schema recommendation. Fold
> in the citability constraints from Diagnose (answer-first opening, self-contained
> claims, cited sources). Attach the target URL's Baseline snapshot so the "before" is
> on the brief. Keep competitor traffic estimates in `needs_tier1`.

## Decision it drives

- **The build-ready work order** for the item — everything a writer/builder needs, with
  its before-value and metric already attached.

## Hand off to

- `design-build` / `content-draft` — the actual build.
- `produce/02-schema-and-build-handoff.md` — the structured-data and indexation deliverables.
- `verify/01-baseline-diff.md` — re-snapshot the target after it ships.
