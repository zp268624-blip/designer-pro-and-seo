# Golden example — design-accessibility (Tier-2: `a11y_static.py`)

Proves the **free, no-tools Tier-2** path of `design-accessibility`: the structural WCAG
checker reads an HTML file (and an optional design-token file) and emits a severity-ranked
findings artifact with **no browser, no Playwright, no network, no key** — the
`structural-a11y` capability's built-in product. Reproducible offline.

## Input

- `sample.html` — a small product page that is mostly correct (html lang, a zoomable
  viewport meta, a skip link, a `<main>` landmark, a labeled email field, one captioned
  image) but carries two deliberate defects: a heading that jumps **h1 -> h3** (a skipped
  `<h2>`) and a product image with **no `alt`**.
- `tokens.json` — a design-system color set in the engine's own token shape
  (`{"colors": {...}}` from `tokens_emit.py` / `gen_palettes.py`). Its `accent` gold
  (`#c9a227`) on the white `bg` is only **2.42:1** — below the 3:1 UI minimum — so the
  token-contrast cross-check has a real failure to report.

## Command

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design/a11y_static.py" \
  --file references/examples/design-accessibility/sample.html \
  --tokens references/examples/design-accessibility/tokens.json \
  --human
```

(From the repo root during development, drop `${CLAUDE_PLUGIN_ROOT}/` and run the bare
`scripts/...` path. Drop `--tokens` for the source-only structural pass; drop `--human`
for machine-readable JSON.)

## Expected free deliverable (Tier 2)

A severity-ranked structural-accessibility report, e.g.:

```
# a11y (structural): references/examples/design-accessibility/sample.html
3 structural issue(s): 0 critical, 1 serious, 2 moderate, 0 minor
  [SERIOUS] img-missing-alt      WCAG 1.1.1  <img src="bench-oak.jpg"> has no alt attribute ...
  [MODERATE] contrast-below-min   WCAG 1.4.11  [accent/bg]  Accent UI color ... is 2.42:1 (needs 3.0:1) ...
  [MODERATE] heading-skip         WCAG 1.3.1  Heading level jumps from h1 to h3 -- do not skip levels.
(structural subset (source-only); a full computed-contrast / keyboard / reduced-motion scan needs Playwright + axe-core)
```

Every finding carries its **WCAG 2.2 success criterion** and a concrete fix; the report is
**severity-ranked** (critical -> serious -> moderate -> minor) and **deterministic** (same
input -> byte-identical output). The closing coverage line is honest about the subset: the
structural checker is a real deliverable on its own, and a **Playwright + axe-core** deep
scan (Tier 1) adds computed contrast on rendered pixels, live keyboard/focus testing,
reduced-motion, and 200%-zoom reflow — the fields this source-only pass cannot see.
