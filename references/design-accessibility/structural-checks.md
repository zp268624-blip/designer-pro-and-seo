# Structural accessibility checks — the `a11y_static.py` catalog

Durable knowledge for the free Tier-2 path of `design-accessibility`: **what the
source-only checker judges, how it ranks findings, and why each check maps to a WCAG 2.2
success criterion.** This is the artifact `qa-gate` (phase 3) and `design-build` act on
when no browser is connected. Knowledge, not steps — the run procedure lives in the
SKILL's `## Steps`; the contrast math lives in `references/shared/wcag-contrast-rules.md`.

## Why "structural" is a real deliverable (and where it stops)

A large, high-value slice of WCAG failures is decidable from HTML source alone —
missing alt, an unlabeled input, a page with no `lang`, a heading tree with a hole.
`a11y_static.py` (stdlib `html.parser`, offline, deterministic) reports exactly that
slice and **says so**: its closing `coverage` line states that a full computed-contrast /
keyboard / reduced-motion / 200%-zoom scan needs Playwright + axe-core (Tier 1). It never
implies full coverage — the honesty is the point.

## The severity model

Four tiers, ranked most-urgent first (findings are stable-sorted by tier, then code):

| Tier | Meaning | Example checks |
|---|---|---|
| **critical** | Blocks a user from completing a task | a form control with no accessible name |
| **serious** | A major barrier for a whole user group | missing `alt`; no `lang`; no viewport; zoom disabled; body-text contrast fail |
| **moderate** | A real problem with a workaround | skipped heading level; no `main` landmark; UI-color contrast fail |
| **minor** | Best-practice / friction | no skip link; more than one `<h1>` |

## The check catalog

| Code | Tier | WCAG SC | What trips it | The fix it names |
|---|---|---|---|---|
| `img-missing-alt` | serious | 1.1.1 | an `<img>` with **no** `alt` attribute (an explicit `alt=""` is decorative and passes) | add descriptive alt, or `alt=""` if purely decorative |
| `heading-no-h1` | serious | 1.3.1 | headings exist but there is no `<h1>` | give the page one top-level heading |
| `heading-skip` | moderate | 1.3.1 | a heading level jumps by more than one (e.g. h1 -> h3) | do not skip levels |
| `heading-multiple-h1` | minor | 1.3.1 | more than one `<h1>` | prefer exactly one |
| `control-no-label` | critical | 4.1.2 / 3.3.2 | an `input`/`select`/`textarea` with no accessible name | `<label for>`, a wrapping `<label>`, or `aria-label` |
| `html-no-lang` | serious | 3.1.1 | `<html>` missing or empty `lang` | set `lang` (e.g. `lang="en"`) |
| `no-viewport-meta` | serious | 1.4.10 | no responsive `<meta name="viewport">` | add `width=device-width, initial-scale=1` |
| `viewport-zoom-blocked` | serious | 1.4.4 | viewport sets `user-scalable=no` or `maximum-scale<=1` | remove the zoom lock |
| `no-main-landmark` | moderate | 1.3.1 | no `<main>` and no `role="main"` | wrap primary content in `<main>` |
| `no-skip-link` | minor | 2.4.1 | no in-page anchor that says "skip" or targets a main/content id | add a skip-to-content link |
| `contrast-below-min` | serious / moderate | 1.4.3 / 1.4.11 | a design-token color pair below its ratio (only with `--tokens`) | adjust the token so the pair clears its ratio |

## How labeling is decided (`control-no-label`)

A control has an accessible name only when **any** of these resolves to **non-empty**
text: it is wrapped by a `<label>` with text; a `<label for="…">` with non-empty text
points at its `id`; it has a non-empty `aria-label`; its `aria-labelledby` points at an
element with non-empty text; or it has a non-empty `title`. An **empty** label (a bare
`<label for>` or a whitespace-only wrapping `<label>`) carries no accessible name, so the
control is still flagged unlabeled. A
**placeholder is deliberately not accepted** — placeholder text disappears on input and is
not a substitute for a label. `type=hidden|submit|reset|button|image` inputs are exempt
(hidden has no UI; the button family names itself from its value).

## The token-contrast cross-check (`--tokens`)

When a design-system token file is supplied, the checker cross-checks the color slots the
engine actually emits — `text`, `bg`, `surface`, `primary`, `on_primary`, `accent` — using
`gen_palettes`'s own `relative_luminance` / `contrast_ratio` (one source of truth, not a
re-implementation). Each pair fires only when both colors are present:

| Pair | Minimum | Rationale |
|---|---|---|
| `text` / `bg`, `text` / `surface` | 4.5:1 | body text (WCAG 1.4.3) |
| `on_primary` / `primary` | 4.5:1 | button-label text |
| `primary` / `bg`, `accent` / `bg` | 3:1 | UI component / large graphic (WCAG 1.4.11) |

Accepted token shapes: the engine-internal `{"colors": {slot: "#hex"}}`, the W3C
`{"color": {slot: {"value": "#hex"}}}` shape `tokens_emit.py --format json` writes, and
bare top-level `slot: "#hex"` keys. 3- and 6-digit hex are both normalized.

## Clean-room note

The catalog, severity mapping, WCAG-SC assignments, and the token-pair selection are
authored from first principles + the public WCAG 2.2 standard for **this plugin's own
engine** (the token slots come from `tokens_emit.py` / `gen_palettes.py` field needs), with
no inspiration source opened. The contrast thresholds are the public WCAG minimums recorded
once in `references/shared/wcag-contrast-rules.md`.
