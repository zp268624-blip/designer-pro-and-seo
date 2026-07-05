# Diagnose · Roll the findings into one honest health score

**Loop stage:** Diagnose — collapse many findings into one anchor number + weakest category.
**When to run:** after the technical and GEO audits, to close the Diagnose stage.

A pile of findings is not a plan. This prompt rolls the audit results into a single
health score and — critically — a **weakest-category** signal, so the roadmap has an
honest anchor for where to spend first.

## Evidence to gather (free Tier-2)

- `scripts/workflow/audit_aggregate.py` — aggregates per-specialist scores into one
  health score **re-normalized over the specialists actually run**, so a skipped
  specialist is not a silent zero that drags the number down dishonestly. Its own weight
  table is deterministic.
- The upstream `seo-audit` orchestrator's specialist outputs (technical, GEO, schema,
  sitemap, image, and any conditional specialists the business type triggered) are the
  inputs it normalizes.

`needs_tier1`: any specialist that itself depends on a connector (e.g. backlinks,
GSC-based coverage) contributes only its free-path score; the connector-only depth is
carried forward as `needs_tier1`, not folded in as a fabricated value.

## The prompt

> Aggregate the audit into one health score for {domain}. Feed only the specialists that
> actually ran; let the aggregator re-normalize so a skipped specialist is excluded, not
> zeroed. Report the composite score, the per-category breakdown, and the **single
> weakest category**. State plainly which specialists ran on the free path and which are
> partial pending a connector (list those under `needs_tier1`). Do not present a score as
> complete if a heavy category was connector-gated and skipped — say what is missing.

## Decision it drives

- **The anchor number** the plan improves against, and the **weakest category** that
  earns the first budget.
- **The category weights** that seed Prioritize's impact axis.

## Hand off to

- `prioritize/01-impact-effort-intent-scoring.md` — the weakest category tilts impact
  scoring toward the findings that move the number most.
- `verify/02-monitor-and-loop-back.md` — the score is itself a tracked metric across cycles.
