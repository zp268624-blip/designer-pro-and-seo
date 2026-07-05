---
name: design-build
description: Generate distinctive, production-grade frontend UI code from a design system — starting from an on-brand, accessible, rendered HTML scaffold and elaborating with taste that avoids the generic-AI-slop aesthetic. Trigger when the user says "build the site", "make the UI", "design and code", "create a landing page", "build a component", or wants polished frontend that looks intentional rather than templated.
---

# design-build

**Family:** design
**Status:** Stable

## Purpose

The frontend code generator — and the payoff of the whole design loop. It takes a
design system (from `design-system-gen`) and **renders a real, on-brand starting
page** via `render_page.py` (semantic HTML5, the system's actual palette/type/
effects as CSS variables, `prefers-reduced-motion` fallback, `:focus-visible`
states, contrast-safe buttons), then elaborates it with taste. The differentiator
is the anti-slop discipline: distinctive type, color, and interaction instead of
the default gradient-purple, rounded-corner look — grounded in the chosen style's
characteristics from `data/ui-styles.csv`.

## Triggers

- "build the site" / "make the UI" / "design and code"
- "create a landing page" / "build a component"
- "make this beautiful" / "production-grade frontend"

## Inputs

- Design system (from `design-system-gen`, or "generate one")
- Page/component spec (from `blast-prompt`, or free-text)
- Stack (HTML+CSS+JS | React | Next.js | Vue | Svelte | Astro)
- Variants (1 = single build; 2+ = invokes `parallel-build`)

## Steps

1. **Get the design system.** Run `design-system-gen` if none exists; save JSON.
2. **Render the on-brand scaffold** — a real, accessible starting point, not a blank
   page:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design/render_page.py" --design-json ds.json --out page.html   # use `py` on Windows if python3 is absent ($env:CLAUDE_PLUGIN_ROOT in PowerShell)
   ```
   (or `--product-type/--industry/--keywords` to run the engine inline).
3. **Elaborate with taste (anti-slop pass).** Replace placeholder copy (use
   `copywriting`), shape the sections to the brief, and add distinctive details that
   match the style's `characteristics` from `data/ui-styles.csv` — reject the
   generic AI look. Honor `data/ux-rules.csv` (one primary CTA, contrast, etc.).
   Apply the tell→build-move mapping and the chart-handling guidance in
   `references/design-build/anti-slop.md` (it applies the shared
   `references/shared/anti-slop-principles.md` rubric at build time). When a section
   needs a **chart**, let the data shape pick it deterministically rather than
   defaulting to a bar or pie:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design/gen_charts.py" --shape time-series-multi --series 4 --colors "#1f77b4,#ff7f0e"   # use `py` on Windows
   ```
   It returns a chart type, an A/B/C accessibility grade + fallback, a `volume_warning`
   when the series/point count overflows the chart's readable band, and (with
   `--colors`) a series-color contrast check reusing the engine's WCAG luminance. The
   reasoning behind the shape→chart table is in
   `references/design-build/chart-selection.md`.
4. **Target the stack.** For HTML+CSS+JS, build straight from the scaffold. For
   React/Vue/etc., translate the scaffold's structure + tokens into components
   (use `design-tokens-emit` for the token file).
5. **Variants.** If the user wants 2+, hand the brief + design system to
   `parallel-build`.
6. **Pre-delivery.** Run `design-accessibility` and `qa-gate` before handoff.

## Outputs

| Output | What it contains | Format | Quality bar (how it is scored) |
|---|---|---|---|
| Built UI | Production frontend elaborated from the rendered on-brand scaffold | HTML/CSS/JS or framework components | Clears the intentionality checklist and passes the swap test in `references/design-build/anti-slop.md`; keeps the scaffold's a11y guarantees (semantic HTML, focus-visible, reduced-motion, AA contrast) |
| Build manifest | Tokens used, sections built, what was elaborated vs. scaffolded, and the one-sentence reason for each brand deviation | md / JSON | Every non-default choice is defensible in one sentence; no unexplained default shipped |
| Charts / data marks (if any) | Chart type matched to data shape, series colors from tokens, text alternative | inline SVG / component | Mark fits the data shape; every series/label clears AA; meaning never by hue alone; no fabricated data point |

Filed to: the user's project workspace, never into the plugin.

## Error Handling

| Condition | Detection | Behavior (degrade, never fail) | User-facing message |
|---|---|---|---|
| No design system yet | no design-system JSON provided | run `design-system-gen` first, then build | "Generated a design system first so tokens stay consistent." |
| Renderer script unavailable | `render_page.py` missing or errors | build from the design-system JSON by hand using the same tokens/a11y contract | "Scaffold renderer unavailable — built from tokens directly; a11y contract preserved." |
| Copy is placeholder | headline/body still generic on review | route to `copywriting` for concrete, specific copy before handoff | "Replaced placeholder copy — generic text is slop, not a shippable draft." |
| 2+ variants requested | user asks for variants | hand brief + design system to `parallel-build` (shared tokens) | "Dispatching N variants via parallel-build; all share one token set." |
| Internal-tool build | user requests "default styling" mode | skip the distinctiveness pass; keep the accessible baseline | "Built the plain accessible baseline — skipped the distinctiveness pass as requested." |
| Bad / empty spec | nothing to build against | ask for the page/component spec; invent nothing | "Give me the page or component spec (or say 'landing page') and I'll build it." |

## Dependencies

- `scripts/design/render_page.py` (required) — Python 3.10+, standard library only
- `design-system-gen` (tokens), `data/ui-styles.csv` + `data/ux-rules.csv` (taste
  constraints), `copywriting` (real copy), `design-tokens-emit` (component token
  files)
- `scripts/design/gen_charts.py` + `data/chart-types.csv` (optional — deterministic
  data-shape → chart recommendation with an a11y grade + series-color contrast check;
  method in `references/design-build/chart-selection.md`)

## Notes

The renderer guarantees a baseline that's already semantic, responsive, and
accessible — so the human/taste effort goes into distinctiveness, not boilerplate.
For internal tools, the user can request "default styling" mode to skip the
distinctiveness pass.

Related: for 2+ variants this skill hands the brief + tokens to `parallel-build`
(Step 5), which runs `design-build` per variant. That is a prose reference, not a
`Dependencies` edge, so the dependency graph stays acyclic.
