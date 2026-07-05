# Prioritize · Sequence the dated, dependency-aware roadmap

**Loop stage:** Prioritize — order the ranked backlog into time, respecting what blocks what.
**When to run:** after scoring, to close the Prioritize stage.

A ranking is not yet a roadmap. This prompt sequences the scored backlog across the time
horizon so blockers precede the work they gate, and attaches a measurement to every item
so the plan stays honest into Verify.

## Evidence to gather (from prior stages, all free Tier-2)

- The **scored backlog** from `prioritize/01`.
- **Blocking dependencies** from Diagnose: a page with a broken canonical or a noindex
  must be fixed before a brief is written onto it; a robots policy fix precedes any
  citability restructure on the same section.
- **The measurement per item** — each task's before-value from the `drift_baseline.py`
  snapshot (Baseline) plus the metric that will prove it: element change (drift-tracked),
  health-score movement (`audit_aggregate.py`), local SoLV (`geogrid.py`), or a
  `needs_tier1` metric (rankings/traffic) that a connector will read later.

`needs_tier1`: velocity assumptions (how fast a change ranks) are never asserted as fact —
sequence on effort and dependency, and label ranking/traffic outcomes as connector-read.

## The prompt

> Sequence the scored backlog for {domain} across {3 / 6 / 12 months}. Order so that every
> blocking technical or policy fix lands before the content that depends on it. Group into
> phases; for each item give the change, the owner-effort, its dependency (if any), and —
> mandatory — the single metric that will prove it worked, drawn from the Baseline
> snapshot or listed as `needs_tier1`. Emit three artifacts: a Gantt-style markdown
> roadmap, a prioritized investment list (highest-leverage first), and a measurement plan
> that pairs each task with its metric. No task ships without a metric.

## Decision it drives

- **The multi-month roadmap, investment list, and measurement plan** — the strategy's
  primary deliverables, dependency-correct and measurable.

## Hand off to

- `produce/` — the top-of-roadmap items become build-ready briefs.
- `verify/` — every task already carries the metric Verify will test.
