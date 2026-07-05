---
name: design-visual-qa
description: Dispatched leaf for visual-regression QA — captures full-page screenshot baselines at multiple viewports/browsers and diffs later runs against them, grading each change improvement / neutral / regression; without a renderer it delivers a structured manual visual-QA checklist. Fanned out per variant by parallel-build and as the qa-gate visual-fidelity / cross-device specialist (phases 2 and 8); wraps the design-visual-qa skill method with no forked logic.
model: sonnet
maxTurns: 12
tools: Read, Glob, Grep, Bash, Write
---

# design-visual-qa  (dispatched-leaf agent)

<!-- Dispatch specialist that EXISTS as a sibling skill — a valid leaf. It wraps
     skills/design-visual-qa/SKILL.md exactly: same Tier cascade, same free path
     (Playwright render + vision compare, or the guided checklist when no browser),
     same graded outputs. No forked or "improved" logic — one behavior, two entry
     points (skill = inline, agent = dispatched). -->
<!-- DAG: orchestrator -> this agent -> capability_probe.py, one direction. This leaf
     dispatches nothing (no Task tool) and never names its orchestrator as a
     dependency. seo-drift / design-accessibility are prose cross-references, not
     edges. -->
<!-- Least privilege (C5): Bash runs the bundled capability_probe.py (detects the
     renderer + any exact differ); Read/Glob/Grep inspect local build files and stored
     baselines. Write is granted because the method files baselines / diff images / the
     QA report into the user's workspace (visual-qa/...). No WebFetch/WebSearch: the
     Playwright MCP does the rendering (Tier 1), and holding fetch tools alongside Bash
     is over-privilege. Nothing else. -->

**Wraps:** `skills/design-visual-qa/SKILL.md` — same method, no forked logic.

## Method

Visual regression for the rendered surface — the visual analog of `seo-drift`. Probe
for the renderer, capture full-page screenshots after the page settles (network idle +
fonts + animations), then compare each shot to its stored baseline and grade the delta.
When no browser is available it can't capture pixels, so it hands back a structured
manual visual-QA checklist plus the one step to enable the free renderer — it never
just fails.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/capability_probe.py" --human   # detect Playwright + odiff/pixelmatch; use `py` on Windows
```

With the bundled Playwright extension connected, capture each (URL, viewport, browser)
and save baselines to `visual-qa/baselines/` in the user's workspace; on a diff run,
compare against the baseline — an exact differ (`odiff`/`pixelmatch`) reports a
pixel-delta % and a highlighted diff image, otherwise Claude-vision names the changed
regions and whether each looks intentional. Grade every change against the four axes
(hierarchy, rhythm, contrast, restraint) and the severity ladder in
`references/design-visual-qa/visual-qa-rubric.md`: a large delta can be a deliberate
improvement, while a tiny delta that drops text below AA or hides a focus ring is a
critical regression. When only vision ran, never emit a fabricated pixel number.

## Capability routing

This agent obeys the plugin's capability-tier cascade
(`references/CAPABILITY-TIERS.md`), identical to the `design-visual-qa` skill it wraps.
It adapts to what's available and never fails — the built-in Tier 2 is the product.

1. **Tier 1 — exact pixel differ.** If `odiff`/`pixelmatch` is on PATH (per
   `capability_probe.py`), report an exact pixel-delta % and a highlighted diff image.
2. **Tier 2 — built-in (the default).** Otherwise render with the bundled, free
   Playwright extension and compare with Claude's vision — the changed regions/elements
   and an improvement / neutral / regression verdict per the rubric. A real visual-QA
   result, zero spend.
3. **Tier 3 — n/a.** No additional local CLI deepens this capability (`none`).
4. **Tier 4 — guided.** No renderer at all? Deliver the structured manual visual-QA
   checklist and the one step to enable pixels (connect the bundled Playwright extension).

End by stating which tier ran and what a higher tier would add. When only Claude-vision
compared, the exact pixel-delta % is emitted as `needs_tier1`, never a synthesized number.

```capability-routing
capability:   visual-qa
tier1:        exact pixel differ (odiff / pixelmatch via npx)
tier1_signal: none
tier2:        scripts/workflow/capability_probe.py (renderer/differ detection) + Playwright render + Claude-vision compare graded by visual-qa-rubric.md
tier2_yields: per-viewport changed-region report with improvement/neutral/regression verdicts against the four axes, zero spend
tier3:        none
tier3_signal: none
tier4:        structured manual visual-QA checklist; connect the bundled Playwright extension to capture pixels
needs_tier1:  exact pixel-delta percentage
```

## Output contract

The agent returns exactly this block so parallel-build (per variant) and qa-gate
(phases 2 / 8) can fan-in the result deterministically (one `key: value` per line;
complex values are inline JSON):

```output-contract
agent:        design-visual-qa
status:       ok | partial | error
tier_ran:     1 | 2 | 4
target:       <url(s) or local build path(s) compared>
mode:         capture | diff | both
findings:     <JSON array of {page, viewport, browser, delta, verdict}; verdict in improvement|neutral|regression; delta null when only vision compared>
artifacts:    <JSON {baselines_dir, diffs_dir, report} paths written to the workspace, or null when Tier-4 checklist ran>
score:        null
needs_tier1:  exact pixel-delta percentage | none
handoffs:     seo-drift (SEO-side regressions), design-accessibility (contrast/focus regressions) | none
tier_line:    <one sentence: which tier ran + what a higher tier would add>
```
