# Baseline · Capture the current state as a frozen snapshot

**Loop stage:** Baseline — freeze the "before" so "did it move?" is answerable later.
**When to run:** immediately after the inventory, before any change is planned.

A strategy is only honest if it can prove its work. This prompt captures a durable,
diffable snapshot of the SEO-critical elements on the pages that matter, so every
roadmap task gets a real before-value and the Verify stage has something to diff against.

## Evidence to gather (free Tier-2)

- `scripts/seo/drift_baseline.py` — captures each URL's SEO-critical elements into a
  local SQLite store (`./.seo-drift/baselines.db` in the user's workspace, never inside
  the plugin) with `url` / `label` / `captured_at` promoted to indexed columns. It reuses
  the one canonical capturer and the one SSRF-guarded loader, so `--file` (offline) and
  `--url` behave identically and safely.
- The captured element set is fixed and known: `meta_robots`, `canonical`, `title`, `h1`,
  `schema_blocks`, `meta_description`, `og_*`, `h2_count`, `word_count`. That list is
  exactly what the Verify stage's severity engine (rules D1..D14) later scores — so what
  you baseline is what you can prove.

`needs_tier1`: current rankings / impressions / clicks are never captured here (this
snapshot is on-page elements only) — they are a GSC/GA4 field, listed under `needs_tier1`.

## The prompt

> Capture a labeled baseline snapshot of {target URLs} into the drift store before we
> change anything. Use a stable `--label` per cycle (e.g. `q3-baseline`) so the trend
> reads cleanly later. Prefer the shortlist of pages the plan will actually touch —
> money pages, pillars, and any page a diagnosed defect sits on — over a blanket capture.
> Record the `captured_at` you used so the snapshot is reproducible. Confirm the store
> lives under the user's workspace. Output the list of snapshotted URLs and their labels;
> note that rankings and traffic are not in this snapshot and belong to `needs_tier1`.

## Decision it drives

- **The frozen measurement line** every later "did it move?" compares against — the
  before-value attached to each roadmap task.
- **Which pages are under measurement** this cycle (the snapshot shortlist).

## Hand off to

- `verify/01-baseline-diff.md` — this snapshot is the diff partner after the work ships.
- `prioritize/` — each task inherits its before-value from the matching snapshot row.
