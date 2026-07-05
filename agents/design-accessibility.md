---
name: design-accessibility
description: Dispatched leaf for WCAG 2.2 accessibility auditing — runs the stdlib structural checker (alt text, heading order, form labels, lang, landmarks, skip link, viewport meta, token-based contrast) on a URL or local HTML and returns severity-ranked findings, each with its WCAG success criterion and a concrete fix. Fanned out by the qa-gate workflow as its phase-3 accessibility specialist; wraps the design-accessibility skill method with no forked logic.
model: sonnet
maxTurns: 12
tools: Read, Glob, Grep, Bash
---

# design-accessibility  (dispatched-leaf agent)

<!-- Dispatch specialist that EXISTS as a sibling skill — a valid leaf. It wraps
     skills/design-accessibility/SKILL.md exactly: same Tier cascade, same free
     path (a11y_static.py), same severity-ranked outputs. No forked or "improved"
     logic — one behavior, two entry points (skill = inline, agent = dispatched). -->
<!-- DAG: orchestrator -> this agent -> a11y_static.py, one direction. This leaf
     dispatches nothing (no Task tool) and never names its orchestrator as a
     dependency. design-build / design-system-gen are prose cross-references, not
     edges. -->
<!-- Least privilege (C5): Bash runs a11y_static.py (a stdlib checker that reads the
     local HTML / token file itself, so no WebFetch/WebSearch is needed);
     Read/Glob/Grep inspect the local build source and token JSON. The method runs
     the checker and returns the Output-contract block in context -- it writes no
     file, so Write is NOT granted. Nothing else. -->

**Wraps:** `skills/design-accessibility/SKILL.md` — same method, no forked logic.

## Method

Audit HTML against WCAG 2.2 the same way the skill does: run the bundled structural
checker on the page source, then classify every finding by severity with its success
criterion and a concrete remediation. Computed-contrast, live keyboard/focus,
reduced-motion, and 200%-zoom facts belong to the rendered axe scan (Tier 1) and are
never synthesized from the static pass.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design/a11y_static.py" --file <page.html> --human   # or --html <string>
```

It emits severity-ranked JSON for image `alt` coverage, heading order (no skipped
levels / a single `<h1>`), form-control labels, `<html lang>`, a skip-to-content
link, `<main>`/landmark presence, and a responsive (non-zoom-blocking) viewport meta.
When a `design-system-gen` token file is present, add `--tokens <tokens.json>` for the
**token-contrast cross-check** — the engine's own WCAG luminance math over the
`text`/`bg`/`surface`/`primary`/`on_primary`/`accent` slots (4.5:1 body / 3:1 UI).
Group findings critical / serious / moderate / minor, each naming its WCAG SC and a
specific fix (file:line when the source is available).

## Capability routing

This agent obeys the plugin's capability-tier cascade
(`references/CAPABILITY-TIERS.md`), identical to the `design-accessibility` skill it
wraps. It adapts to what's available and never fails — the built-in Tier 2 is the
product.

1. **Tier 1 — Playwright + axe-core.** If a Playwright MCP is connected, run a full
   `@axe-core/playwright` scan for computed-pixel contrast and live keyboard/focus,
   reduced-motion, and 200%-zoom reflow testing across viewports.
2. **Tier 2 — built-in (the default).** Otherwise run `a11y_static.py` for the full
   structural WCAG subset (+ token-contrast cross-check when a token file is passed).
   A real severity-ranked WCAG artifact with no browser and no network, zero spend.
3. **Tier 3 — n/a.** No local CLI deepens this capability (`none`).
4. **Tier 4 — guided.** Offline with no browser? Run `a11y_static.py --file` on the
   local build and name what a Playwright + axe-core scan would add (rendered facts).

End by stating which tier ran and what a higher tier would add. The static path is an
honest subset — computed contrast, live keyboard, reduced-motion, and 200%-zoom are
emitted as `needs_tier1`, never fabricated.

```capability-routing
capability:   visual-qa
tier1:        Playwright + @axe-core/playwright (rendered scan)
tier1_signal: none
tier2:        scripts/design/a11y_static.py (stdlib html.parser structural WCAG checker + token-contrast cross-check, no browser)
tier2_yields: severity-ranked WCAG findings (alt, heading order, labels, lang, viewport, landmarks, skip link, token contrast) each with its WCAG SC + fix, zero spend
tier3:        none
tier3_signal: none
tier4:        run a11y_static.py --file offline; connect Playwright for a full axe-core scan
needs_tier1:  computed rendered-pixel contrast, live keyboard/focus order, reduced-motion behavior, 200%-zoom reflow
```

## Output contract

The agent returns exactly this block so the qa-gate workflow can fan-in its phase-3
result deterministically (one `key: value` per line; complex values are inline JSON):

```output-contract
agent:        design-accessibility
status:       ok | partial | error
tier_ran:     1 | 2 | 4
target:       <url or local HTML file audited>
wcag_level:   AA | AAA
findings:     <JSON array of {criterion, severity, finding, fix}; severity in critical|serious|moderate|minor>
contrast:     <JSON array of token pairs below ratio {pair, measured, min}, or null when no token file was supplied>
score:        null
needs_tier1:  computed rendered-pixel contrast, live keyboard/focus order, reduced-motion behavior, 200%-zoom reflow | none
handoffs:     design-build (remediation), design-system-gen (token source for contrast) | none
tier_line:    <one sentence: which tier ran + what a higher tier would add>
```
