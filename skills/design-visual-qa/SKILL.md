---
name: design-visual-qa
description: Capture full-page screenshot baselines at multiple viewports and browsers, then diff later runs against them to catch unintended rendering changes. Renders with the bundled (free) Playwright extension and compares with Claude's vision, adding an exact pixel-diff CLI for precise deltas when one is installed. Without a browser, delivers a manual visual-QA checklist and the one step to enable rendering. Trigger when the user says "visual qa", "visual regression", "screenshot diff", "pixel diff", "did anything change visually", "compare against baseline", or "before and after screenshots".
---

# design-visual-qa

**Family:** design
**Status:** Stable

## Purpose

Visual regression for the rendered surface — the visual analog of `seo-drift`.
Captures snapshots at multiple viewports and compares them against prior baselines
to catch unintended rendering changes. It is **tool-aware**: rendering uses the
bundled, free Playwright extension; comparison uses Claude's vision by default (and
an exact pixel-diff CLI for precise deltas when one is installed). Without a browser
it can't capture pixels — so it delivers a structured manual visual-QA checklist and
the single step to enable the free renderer, rather than failing.

Use cases: pre/post refactor, pre/post deploy (staging vs prod), component/token
updates, and cross-browser drift.

## Triggers

- "visual qa" / "visual regression"
- "screenshot diff" / "pixel diff"
- "did anything change visually"
- "compare against baseline"
- "before and after screenshots"

## Inputs

- Target URL(s) or local build paths
- Viewports (default: 375, 768, 1280, 1920)
- Browser(s) (default: chromium; optional firefox, webkit)
- Baseline mode: capture | diff | both
- Threshold for "changed" (pixel-diff % when an exact differ is present; otherwise a
  qualitative materiality call)

## Steps

1. **Detect the renderer.** Confirm the Playwright MCP is connected, then run
   the capability probe to see if an exact differ (`odiff`/`pixelmatch` via `npx`)
   is available:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/capability_probe.py"    # use `py` on Windows if python3 is absent; in PowerShell the variable is $env:CLAUDE_PLUGIN_ROOT
   ```
2. **Capture.** For each (URL, viewport, browser): load, wait for network idle +
   fonts + animations settled, then full-page screenshot.
3. **Baseline vs diff.**
   - `capture`: save baselines to `visual-qa/baselines/` in the user's workspace.
   - `diff`: compare each shot to its baseline. Exact differ present → pixel-delta %
     + highlighted diff image. Otherwise → Claude-vision comparison reporting the
     specific regions/elements that changed and whether each looks intentional.
4. **Aggregate** which pages/viewports drifted and by how much (or how materially).
   Grade each change against the four axes (hierarchy, rhythm, contrast, restraint)
   and the severity ladder in `references/design-visual-qa/visual-qa-rubric.md` — a
   large delta can be a deliberate improvement, while a tiny delta that drops text
   below AA or hides a focus ring is a critical regression.
5. **Report which tier ran** (per the plugin's capability-tier cascade,
   `references/CAPABILITY-TIERS.md`: Tier 1/2 = Playwright render + exact-differ-or-
   Claude-vision compare; Tier 4 = no browser, guided checklist) and, if no browser
   was available, the one step to enable it (connect the bundled Playwright extension).

## Outputs

| Output | What it contains | Format | Quality bar (how it is scored) |
|---|---|---|---|
| Baselines | `visual-qa/baselines/<page>-<viewport>-<browser>.png` | PNG per (page, viewport, browser) | Captured only after network idle + fonts + animations settle, so a baseline is stable, not mid-render |
| Diff images | `visual-qa/diffs/<run-date>/...` | PNG (when an exact differ ran) | Highlights the changed regions; pixel-delta % reported when a differ is present |
| QA report | `visual-qa/report-<date>.md` — drifted pages/viewports + per-change verdict + tier | md, grouped Critical/High/Advisory | Every change classified improvement / neutral / regression against the four axes; states which tier ran; no fabricated pixel number when only Claude-vision ran |

Filed to: the user's project workspace. A change is judged by the rubric in
`references/design-visual-qa/visual-qa-rubric.md`, not by pixel delta alone.

## Error Handling

| Condition | Detection | Behavior (degrade, never fail) | User-facing message |
|---|---|---|---|
| No browser / Playwright absent | MCP not connected (capability probe) | deliver the Tier-4 manual visual-QA checklist + the one step to enable the free renderer | "No renderer — here's a manual visual-QA checklist. Connect the bundled Playwright extension to capture pixels." |
| No exact pixel differ | `odiff`/`pixelmatch` not found by the probe | compare with Claude's vision; report changed regions qualitatively | "No exact differ — used vision comparison; add odiff/pixelmatch for pixel-delta %." |
| No baseline yet | `capture`/`diff` target has no stored baseline | capture it as the new baseline instead of erroring | "No baseline for <page> — captured one; re-run after your change to diff." |
| Page never settles | network idle / fonts / animation wait times out | capture at the timeout and flag the shot as possibly unsettled | "<page> didn't settle — captured at timeout; treat its diff as advisory." |
| Bad / unreachable target | URL fails validation or won't load | report the target error; capture nothing for it | "<url> is unreachable / invalid — skipped it; other targets captured." |

## Dependencies

- Playwright extension (`extensions/playwright/`) — free, bundled; required to
  capture. Without it, the skill runs its Tier-4 guided path.
- Optional: an exact pixel-diff CLI (`odiff`/`pixelmatch` via `npx`) for precise
  deltas; Claude-vision comparison is the default and needs nothing extra.
- `scripts/workflow/capability_probe.py`

## Notes

Pairs with `seo-drift` for a complete "did anything change" picture — drift catches
SEO regressions, visual-qa catches rendering regressions. Comparison defaults to
Claude's vision so no pixel-diff dependency is required for a useful result.
