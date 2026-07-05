# Anti-slop at build time — applying the rubric while you code

Durable knowledge for `design-build`: how the eight tells of slop translate into
concrete decisions while elaborating a rendered scaffold into finished frontend, plus
the chart-handling guidance the general rubric doesn't cover. The evaluative rubric
itself — the eight tells, the intentionality checklist, the swap test — lives once in
`references/shared/anti-slop-principles.md`; **read that first**, this file is the
build-time application layer, not a restatement.

`design-build` starts from a real, on-brand, accessible scaffold (`render_page.py`),
so the baseline already clears the "default everything" tell. The taste effort is
therefore *additive*: every elaboration must move the page further from generic, never
back toward it.

## The build-time stance

The scaffold gives you correct bones (semantic HTML, the system's actual tokens,
focus-visible, reduced-motion, contrast-safe buttons). Slop creeps back in during
elaboration — when placeholder copy, stock decoration, or a default component gets
shipped because it was the fast choice. The stance: **treat every unexplained default
as a finding to elaborate, not a thing to ship.** For each block you touch, be able to
state in one sentence why it is this and not the default. If you can't, it's slop.

## Tell → build move

Each tell from the shared rubric maps to a specific thing you do (or refuse to do) in
code:

| Slop tell | Build-time move |
|---|---|
| No point of view | Pick the page thesis (feel + action) before writing markup; let it veto sections that don't serve it. |
| Default everything | Deviate deliberately on the 1–2 brand axes from the style's `characteristics`; keep the rest disciplined so the deviation reads. |
| Even, characterless rhythm | Build a real type + space scale from the tokens; make the primary thing the biggest / boldest / most isolated — not one of three equal cards. |
| Stock metaphors | Refuse the floating blob / abstract swoosh / rocket-for-launch; use real, subject-specific imagery or an owned illustration style. |
| Decorative motion | Every transition must clarify (reveal hierarchy, confirm an action, show relation) and honor `prefers-reduced-motion` — which the scaffold already wires. |
| Hollow copy | Replace placeholder text via `copywriting` with concrete nouns/verbs and specific claims; if a competitor could paste their name over the headline, rewrite it. |
| Borrowed system | Derive every token from the design system, not from what's popular; each value earns its place. |
| No restraint | Say no to something visible — one accent, one quiet field that makes the loud element land. |

Then run the intentionality checklist from the shared rubric as the acceptance bar
before handing off to `design-accessibility` and `qa-gate`.

## Honor the constraint data

Two CSVs are hard inputs, not suggestions:

- `data/ui-styles.csv` — the chosen style's `characteristics` tell you *which* axes to
  push (type, color, edge, motion) and `avoid_for` tells you where the style is wrong.
- `data/ux-rules.csv` — non-negotiables the build must satisfy: one primary CTA per
  view, contrast minimums, label/affordance rules. A distinctive page that breaks these
  is still slop — restraint and usability are part of the aesthetic, not opposed to it.

## Chart & data-viz handling (build-time)

Charts are where slop and inaccessibility both hide, and the general rubric doesn't
address them. When a build includes a chart, meter, KPI tile, or any data mark:

- **Let the data shape the chart, not the library default.** Match the mark to the
  data shape (trend → line/area; part-to-whole → bar/stacked, not a pie of 8 slices;
  comparison → grouped bars; distribution → histogram). A default pie or a 3-D bar is
  the chart equivalent of the floating blob.
- **Series color comes from the system, and must stay AA-legible.** Draw series colors
  from the design tokens, not a rainbow default. Verify every series/label against its
  background with the same luminance math the engine uses
  (`references/shared/wcag-contrast-rules.md`) — a legend swatch that fails contrast
  fails the build.
- **Never encode meaning by hue alone.** Redundantly encode with label, shape, position,
  or direct annotation so the chart survives color-blindness and grayscale — the chart
  analog of the swap test.
- **Restraint on the chart too.** Kill chartjunk: no gratuitous gridlines, drop
  shadows, gradient fills, or 3-D. Label directly over a floating legend where you can;
  the quiet field that makes the one important number land applies here as well.
- **Honest data only.** A chart must not imply precision the data doesn't have. Never
  render a fabricated or placeholder value as a real data point; if a number is a proxy
  or unavailable, say so in the caption rather than drawing a confident bar.
- **Accessible by structure.** Give every chart a text alternative (a caption or an
  adjacent data table), a real `<title>`/`aria-label`, and a keyboard-reachable source
  if it's interactive — accessibility designed in, not retrofitted.

Where the plugin ships a deterministic chart helper (a `gen_charts` + chart-types data
path), it recommends the mark for the data shape and grades the series-color a11y; the
build move is to honor that recommendation and its fallback rather than override it with
a prettier-looking default. Absent the helper, apply the guidance above by hand.

## See also

- `references/shared/anti-slop-principles.md` — the eight tells + intentionality
  checklist + swap test (the rubric this file applies).
- `references/shared/wcag-contrast-rules.md` — the contrast math for text and series
  colors.
- `data/ui-styles.csv`, `data/ux-rules.csv` — the per-style and global build constraints.
