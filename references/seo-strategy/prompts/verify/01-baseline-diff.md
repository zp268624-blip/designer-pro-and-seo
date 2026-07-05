# Verify · Diff against the baseline to prove the change landed

**Loop stage:** Verify — prove the shipped change did what the roadmap said, and caught no regression.
**When to run:** after each roadmap item ships, against its Baseline snapshot.

This is where the plan earns its honesty. Every task left Prioritize carrying a metric and
a before-value; this prompt captures the after-state and diffs it, so "done" is evidence,
not assertion — and so a silent regression on an untouched element is caught.

## Evidence to gather (free Tier-2)

- `scripts/seo/drift_compare.py` — captures the current snapshot (SSRF-guarded), resolves
  the stored baseline from the `drift_baseline.py` SQLite store, and runs the severity
  engine to produce a severity-ranked change report.
- `scripts/seo/drift_severity.py` — maps each changed element to a tier (critical / high /
  advisory) via rules D1..D14, one per captured element, with a 20% word-count noise floor
  so trivial edits do not raise noise. See `references/seo-drift/severity-model.md`.

`needs_tier1`: ranking/traffic movement is a never-fabricate field — the diff proves the
*on-page element* changed as intended; the *ranking/traffic* outcome is read from a
GSC/GA4 connector and listed under `needs_tier1` until then.

## The prompt

> Verify {this shipped item} against its Baseline snapshot. Capture the target URL now and
> diff it against the stored baseline for the same label. Report the severity-ranked
> changes: confirm the intended element changed (e.g. the new `title`, the added
> `schema_blocks`, the fixed `canonical`) and flag any **unintended** change on an element
> we did not mean to touch — a critical/high regression re-enters the backlog immediately.
> State plainly what the diff proves (the on-page change) and what it does not (ranking /
> traffic movement), listing the latter under `needs_tier1`. Do not claim a ranking gain
> the free path cannot observe.

## Decision it drives

- **Did the change land as intended, and did anything regress** — a pass/fix verdict per task.
- **Which regressions re-enter the backlog** (they become new Prioritize candidates).

## Hand off to

- `verify/02-monitor-and-loop-back.md` — accumulate diffs into a trend across cycles.
- `prioritize/` — critical/high regressions return as scored candidates.
