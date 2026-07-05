# Diagnose · Technical health, severity-ranked

**Loop stage:** Diagnose — find what is broken and how badly, on evidence.
**When to run:** after Baseline; before any content investment is scheduled.

Content investment poured onto a broken technical foundation is wasted. This prompt runs
the deterministic technical checks and separates blocking defects (fix first) from
advisory ones (schedule later), so the roadmap spends in the right order.

## Evidence to gather (free Tier-2)

- `scripts/seo/tech_audit.py` — single-page technical SEO checks (crawlability /
  indexability / meta / canonical / mobile / structured-data presence), encoding the
  public Core Web Vitals targets (INP < 200 ms) and the AI-crawler robots policy. Bad
  input exits non-zero with a JSON error — a failed check is never a silent pass.
- `scripts/seo/page_fetch.py` / `scripts/seo/site_map.py` — the SSRF-guarded fetch and
  discovery backbone the audit runs over; redirect-chain depth and the flag-gated
  SPA-shell signal come from here.

`needs_tier1`: **field** Core Web Vitals (real-user LCP/INP/CLS) are a never-fabricate
field — the free path reports lab-side/heuristic signals against the public targets and
lists field CWV under `needs_tier1` (a free PSI/CrUX key or a GSC connector supplies it).

## The prompt

> Audit the technical health of {the baseline inventory}. Run the per-page technical
> checks across the money pages, the pillars, and a depth-representative sample of the
> rest. Group every finding as **blocking** (indexability, canonical conflicts, robots
> exclusions, redirect chains/loops, noindex on a page we want ranked) or **advisory**
> (meta length, minor mobile issues, non-critical structured-data gaps). For each
> blocking finding, name the page, the defect, and the fix. Report CWV against the public
> targets using lab/heuristic signals only, and list field CWV under `needs_tier1`. Do
> not invent a field number.

## Decision it drives

- **Which defects block content ROI** and must be sequenced *before* new pages ship.
- **The effort estimate** for each technical fix (feeds Prioritize's effort axis).

## Hand off to

- `prioritize/01-impact-effort-intent-scoring.md` — blocking defects enter the backlog
  as high-impact, often low-effort items.
- `produce/02-schema-and-build-handoff.md` — structured-data gaps become build deliverables.
