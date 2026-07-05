---
name: parallel-build
description: Spin up multiple website or page variants in parallel — each in its own git worktree or sibling folder, built by a sub-agent from the same brief and shared design tokens but a different inspiration source — then cherry-pick and merge the best sections into one final. Captures side-by-side comparison screenshots when Playwright is connected; otherwise renders a structured comparison summary. Trigger when the user says "parallel build", "build three versions", "spin up variants", "make 3 sites at once", "side-by-side build", or "different design flavors to compare".
---

# parallel-build

**Family:** build-and-qa
**Status:** Stable

## Purpose

The multi-variant build primitive: instead of one prompt → one site, spawn N
sub-agents (default 3), each in its own worktree/folder, each given a different
inspiration source but the **same brief and the same design tokens**. The user gets
a side-by-side comparison and cherry-picks the best sections into a merged final.

## Triggers

- "parallel build" / "build three versions" / "spin up variants"
- "make 3 sites at once" / "side-by-side build"
- "different design flavors to compare"

## Inputs

- Target (business/page/client) + the brief
- N variants (default 3) and N inspiration sources (one per variant; `html-extract`
  can supply them)
- Output mode: git worktrees | sibling folders

## Steps

1. **Capture** the brief and the N inspiration sources.
2. **Generate shared tokens once** with `design-system-gen` so all variants share a
   coherent palette/type/effects — consistency across variants, distinctiveness via
   inspiration + layout.
3. **Create N output locations** — git worktrees (one per variant) or, if git isn't
   available, sibling folders `variant-1/ … variant-N/`.
4. **Dispatch N build sub-agents in parallel** behind the shared-token barrier — each
   runs the `design-build` skill with the same brief + the one shared token set from
   step 2, differing only by inspiration source. (`design-build` is an orchestrator, so
   each variant runs it as a skill inside its own sub-agent — not as a dispatched-leaf
   agent; the barrier guarantees every variant shares one palette/type/effects system.)
   One-shot each (iterate only if needed).
5. **Collect** outputs and render a side-by-side comparison. When Playwright is
   connected, fan out one `design-visual-qa` agent per variant for screenshot capture
   and cross-variant diffs; otherwise render a structured comparison summary.
6. **Cherry-pick + merge.** The user picks sections from each; assemble the final and
   run `qa-gate` before delivery.

## Outputs

- N variant builds in their output locations
- A side-by-side comparison artifact
- The merged final (after the user picks)

## Dependencies

- `design-system-gen` (required) — generates the shared tokens once so every variant
  shares one palette/type/effects system
- `design-build` (required) — runs the per-variant build inside each sub-agent
- `html-extract` (optional — adds auto-sourced inspiration per variant; free path: user
  supplies the inspiration sources)
- `design-visual-qa` (optional — adds side-by-side comparison screenshots via Playwright;
  free path: structured comparison summary)
- `qa-gate` (optional — adds a structured PASS/FAIL gate on the merged final; free path:
  manual review before handoff)
- Sub-agent dispatch + git worktrees (optional — falls back to sibling folders
  `variant-1/ … variant-N/`)

## Notes

Shared tokens + divergent inspiration is the formula: variants feel like one brand
exploring directions, not three unrelated sites.
