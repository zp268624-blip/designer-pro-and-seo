# Golden example — seo-technical (Tier-2: `tech_audit.py`)

Proves the **free, key-absent Tier-2** path of `seo-technical` produces a real
9-category technical audit with no network and no API key — the `cwv-field`
capability's built-in product. Reproducible offline.

## Input

- `sample-page.html` — a tiny static page seeded with one fixable issue (a mixed
  `http://` link) and one image missing `alt`, plus a healthy title/meta/canonical/
  viewport/lang/JSON-LD set.

## Command

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/tech_audit.py" \
  --file references/examples/seo-technical/sample-page.html --no-network --human
```

(From the repo root during development, drop `${CLAUDE_PLUGIN_ROOT}/` and run the
bare `scripts/...` path.)

## Expected free deliverable (Tier 2)

Prioritized per-dimension findings, e.g.:

- `[HIGH] Mixed content: http:// resources on the page`
- `[MEDIUM] 1/2 <img> missing alt (use seo-image-audit)`
- `[INFO]` lines confirming title, meta description, single `<h1>`, canonical,
  viewport, `lang`, and one JSON-LD block.
- A `[CWV]` line emitting the LCP<2.5s / CLS<0.1 / INP<200ms targets and stating
  that synthetic tools can't measure *field* CWV.

No field-CWV number is fabricated. `needs_tier1` (field CWV via CrUX/PSI, real
Lighthouse score) is satisfied only by adding a free Google key via `seo-google`
(Tier 1). The audit above is complete on its own — the product.
