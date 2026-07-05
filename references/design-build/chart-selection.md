# Chart selection — the data-shape → chart method

Depth for `design-build` when a page needs a chart. Knowledge, not steps: it explains
*why* the engine (`scripts/design/gen_charts.py` over `data/chart-types.csv`) maps a
data **shape** to a chart, so the elaboration pass picks a defensible visualization
instead of the default bar-or-pie reflex. The script is the deterministic front door;
this file is the reasoning behind its table.

## The premise: chart choice is a data decision, not a taste decision

A chart's job is to make one **relationship in the data** legible. The relationship is
fixed by the data's *shape*, so the same shape earns the same chart family every time —
that is why `gen_charts.py` is deterministic. Taste enters later (color, type, spacing,
annotation), never in the "which chart" step. Ask "what is the reader comparing?" and
the shape falls out:

| The reader is comparing… | Data shape | Chart family |
|---|---|---|
| a value over evenly-spaced time | `time-series-*` | line / area / small-multiples |
| a value across nominal categories | `category-compare-*` | bar (vertical → horizontal as labels/counts grow) |
| parts of one whole | `part-to-whole-*` | donut (≤5) → 100%-stacked → treemap |
| two numeric variables | `two-var-*`, `three-var-*` | scatter → density-heatmap → bubble |
| the spread of one variable | `distribution-*` | histogram / box / violin |
| movement between nodes or stages | `flow-*` | sankey / chord / funnel |
| one metric against a target | `single-value-*`, `value-with-trend` | bullet / big-number / KPI-sparkline |
| rank movement | `ranking-*` | slopegraph (two points) / bump-chart (many) |

The full slug list lives in `data/chart-types.csv`; pass the closest slug to
`--shape` and the engine returns the chart, its a11y grade, and a fallback.

## Volume thresholds change the answer, so state them

The *same* shape flips to a different chart as volume grows — a handful of categories
is a vertical bar; forty long-labelled ones is a horizontal bar; eighty is a lollipop.
Each row carries `min_series` / `max_series` / `max_points`, the band it stays readable
in. When the supplied volume overflows that band, `gen_charts.py` does **not** silently
mis-chart: it returns the closest row plus a `volume_warning` that names the fallback
(e.g. 12 trends → "switch to small-multiples"). Treat a `volume_warning` as a
must-resolve, not a suggestion — a spaghetti of 12 lines is a failed chart even if it
renders.

## Accessibility is graded, not assumed

Every row has an A/B/C grade and a concrete `a11y_fallback`:

- **A** — reads without relying on color, and has a clean table equivalent (bar, line,
  histogram, bullet). Default to grade-A shapes when the data allows.
- **B** — legible but needs care: ordering, direct labels, or a value annotation
  (grouped bar, box plot, slopegraph).
- **C** — powerful but hard for non-visual users or at a glance (treemap, sunburst,
  heatmap, sankey, choropleth, radar). Ship these **with** their fallback rendered too
  (an indented table, a pivot table, an edge list), never alone.

A grade-C chart is not banned — it is the right tool for a genuine hierarchy or flow —
but the fallback is part of the deliverable, so the page stays usable when color,
hover, or sight is unavailable.

## Series color is a contrast problem, not a palette-picker problem

Multi-series charts fail accessibility most often on **color**, and the fix is the same
WCAG math the design engine already uses everywhere else. `gen_charts.py --colors`
reuses `gen_palettes.contrast_ratio` (the shared sRGB relative-luminance formula, also
behind `render_page.py`) to check two things against WCAG 1.4.11's 3:1 non-text bar:

1. **Series vs background** — every series mark must clear 3:1 against the chart
   background or it disappears for low-vision readers.
2. **Series vs every other series** — *every unordered pair* of series colors must clear
   3:1 against each other (the grade reflects the worst pair anywhere in the set; adjacent
   pairs are reported as extra detail), or near-identical series are indistinguishable to
   many colorblind readers.

The report grades the set A/B/C and lists concrete fixes. Two colors that are only
1.4:1 apart are not "close enough" — add a pattern, a direct label, or repick. Because
the contrast comes from the same luminance function the palette generator uses, a
chart's series colors and the page's palette are judged on one consistent ruler.

## Honest defaults (the anti-slop stance, applied to charts)

- Prefer a ranked **bar** to a word cloud; area is unreadable as a quantity.
- Prefer a **bullet** or big-number to a gauge; a gauge spends pixels on chrome.
- Start bar value-axes at **zero**; a truncated axis is a lie, not a style choice.
- Cap pie/donut slices at ~5 and always label values — angle alone is imprecise.
- One relationship per chart. If two relationships matter, that is two charts.

## Related

- `data/chart-types.csv` — the shape→chart table the engine reads (our own 9-column
  schema; row counts and columns derived from what `gen_charts.py`/`render_page.py`
  consume, not any external chart taxonomy).
- `references/shared/wcag-contrast-rules.md` — the shared contrast rules and the sRGB
  luminance formula reused for series-color grading.
- `references/design-build/anti-slop.md` — the broader distinctiveness discipline this
  chart stance is one instance of.
