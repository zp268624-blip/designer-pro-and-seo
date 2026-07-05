---
name: design-accessibility
description: Audits HTML against WCAG 2.2 — no-tools structural checks (alt text, heading order, form labels, lang, landmarks, skip link, viewport meta, token-based contrast), plus a full axe-core scan covering computed contrast, keyboard/focus order, reduced-motion, and 200% zoom. Uses Playwright + @axe-core/playwright when connected; otherwise the structural subset runs alone (clearly lower fidelity). Produces a severity-ranked report with per-issue remediation. Trigger when the user says "accessibility check", "a11y check", "wcag audit", "axe scan", "is this accessible", "screen reader check", or "keyboard nav check".
---

# design-accessibility

**Family:** design
**Status:** Stable

## Purpose

A dedicated accessibility skill. Runs **structural WCAG 2.2 checks on any HTML with
no tools required** (the free path) and a **full axe-core scan when Playwright is
installed** (the deep path), producing a severity-ranked report that downstream
skills (`qa-gate`, `design-build`) can act on.

## Triggers

- "accessibility check" / "a11y check" / "wcag audit"
- "axe scan" / "is this accessible"
- "screen reader check" / "keyboard nav check"

## Inputs

- Target URL or local build path
- WCAG level: AA (default) | AAA
- Viewports to test (defaults: 375 / 768 / 1280)
- Optional: a design-system token file (from `design-system-gen`); the token-based contrast check in Step 2 runs only when it is present

## Steps

1. **Detect Playwright.** If available → deep path (step 3). If not → static path
   (step 2). Always say which path ran.
2. **Static WCAG checks** (free path, on the page source): run
   `scripts/design/a11y_static.py --file <page.html>` — a stdlib `html.parser`
   structural checker that emits severity-ranked JSON findings for image `alt`
   coverage, heading order (no skipped levels / one `<h1>`), form-control labels,
   `<html lang>`, a skip-to-content link, `<main>`/landmark presence, and a
   responsive (non-zoom-blocking) viewport meta. When a `design-system-gen` token
   file is present, pass `--tokens <tokens.json>` to add the **token-contrast
   cross-check** (the engine's own WCAG luminance math over the `text`/`bg`/
   `surface`/`primary`/`on_primary`/`accent` slots). See
   `references/design-accessibility/structural-checks.md` for the full check
   catalog + severity model.
3. **Deep axe scan** (Playwright path): for each viewport, run axe-core; test
   keyboard nav (tab order, visible focus, focus traps in modals, escape routes);
   test `prefers-reduced-motion`; test 200% text scaling for truncation/overflow;
   verify computed-style color contrast.
4. **Classify** findings critical / serious / moderate / minor with the WCAG
   success criterion and remediation guidance (file:line when source is available).
5. **Render** the report; note clearly that the static path is a subset and a full
   axe scan needs Playwright.

## Capability routing

Accessibility auditing runs on a two-tier cascade. The **free Tier-2 structural
checker (`a11y_static.py`) is the product** — it delivers a real severity-ranked
WCAG artifact with no browser and no network; a connected Playwright + axe-core
(Tier 1) deepens it with rendered-pixel contrast and live keyboard/motion/zoom
testing. See `references/CAPABILITY-TIERS.md` for the cascade grammar.

```capability-routing
capability:   structural-a11y
tier1:        Playwright + @axe-core/playwright (rendered scan)
tier1_signal: none
tier2:        a11y_static.py (stdlib html.parser structural WCAG checker + token-contrast cross-check, no browser)
tier2_yields: severity-ranked WCAG findings (alt, heading order, labels, lang, viewport, landmarks, skip link, token contrast) with per-issue WCAG SC + fix, zero spend
tier3:        none
tier3_signal: none
tier4:        manual WCAG 2.2 walkthrough; connect Playwright for a full axe-core scan
needs_tier1:  computed rendered-pixel contrast, live keyboard/focus order, reduced-motion behavior, 200%-zoom reflow
```

## Outputs

| Output | What it contains | Format | Quality bar (how it is scored) |
|---|---|---|---|
| Structural WCAG report | Severity-ranked findings (critical/serious/moderate/minor), each with its WCAG 2.2 success criterion + a concrete fix | JSON (default) or ASCII `--human` | every finding names a WCAG SC and a specific remediation; findings are severity-ranked and the run is deterministic (same input → identical output) |
| Token-contrast cross-check | Any design-token color pair below its ratio (4.5:1 body / 3:1 UI), with the measured ratio | rows inside the report (`contrast-below-min`) | only fires with `--tokens`; uses the engine's own WCAG math; reports the exact ratio, never a guess |
| Coverage statement | Which path ran and what a full axe scan would add | one sentence | states the static subset honestly; never implies full-scan coverage |

Filed to: the user's project workspace. The structural path is a genuine subset —
computed-contrast, live keyboard, reduced-motion, and 200%-zoom facts are marked
`needs_tier1` (Playwright + axe-core), never synthesized.

## Error Handling

| Condition | Detection | Behavior (degrade, never fail) | User-facing message |
|---|---|---|---|
| Playwright absent | MCP not exposed / not connected | run the Tier-2 `a11y_static.py` structural checker alone | "Ran Tier 2 (static structural checks). Connect Playwright for computed-contrast + live keyboard/motion/zoom testing." |
| No token file supplied | `--tokens` omitted | run every structural check except the token-contrast cross-check | "Contrast cross-check skipped — pass a design-system token file to grade color pairs." |
| Bad / missing HTML input | `a11y_static.py` validates and exits non-zero with a JSON `error` | report the validation error; analyze nothing invented | "`--file`/`--html` is required or the file is unreadable — here is the expected input." |
| Unparseable `--tokens` JSON | `json.load` raises; script exits non-zero | report the parse error; skip the cross-check, keep structural findings | "Could not parse the token JSON — fixed the path and re-run for the contrast cross-check." |
| Malformed markup | `html.parser` tolerates it | analyze what parses; still emit a report | "Parsed leniently — findings reflect the recoverable structure." |

## Dependencies

- None required for the static path (analyzes provided HTML)
- Playwright extension + `@axe-core/playwright` (optional — adds computed-contrast verification + live keyboard/focus testing + reduced-motion + 200%-zoom checks; free path: the static structural checks in Step 2)

## Notes

Mandatory inside the `qa-gate` workflow (phase 3); also standalone. The static path
catches a real subset of WCAG issues, but only a browser-based axe scan covers
computed contrast and live keyboard behavior — the report says so rather than
implying full coverage.
