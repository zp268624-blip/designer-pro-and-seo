# Design ranker — improve-without-regress diff (legacy raw-overlap -> new weighted-IDF)

> Moat-safe rollout artifact (MASTER-PLAN 6.1, step 5). Regenerate with:
> `py tests/fixtures/gen_ranker_baseline.py --ranker new --diff tests/fixtures/ranker_baseline.json`
> Anchor: `tests/fixtures/ranker_baseline.json` (the CURRENT/legacy ranker, captured before the change;
> `DPS_RANKER=legacy` reproduces it byte-for-byte).

## Scope of change

Full corpus = every product_type (26) x 6 keyword sets (default, own-mood, modern-minimal,
bold-premium, lone-clean, override-brutalist) = **156 inputs**, four dimensions each.

| Dimension | Changed | Why |
|---|---|---|
| **pattern** | 0 | comes straight off the product row; ranker not involved |
| **style** | 0 | every product's `recommended_style` exists in `ui-styles.csv`, so style is decided by the deterministic explicit-style-override SUBSET rule, which is **ranker-independent**. The ranker's style scoring branch only runs when a style name is *not* on file. |
| **palette** | 2 | IDF win (see below) |
| **typography** | 64 | the headline fix (see below) |

**No regressions in the honesty flags:** 0 inputs newly fall below the confidence floor
(no input flips matched -> "no strong match"). 32 inputs gain/lose a `_fallbacks` line,
all of them the new honest **tie-margin** disclosure on a genuine near-tie.

## Why the new picks are better

### The headline fix: `modern-neutral` was a generic-token magnet
Under raw overlap every matched token counts 1, so `modern-neutral` (mood `clean;versatile`,
best_for `saas;dashboards;b2b`, name `modern-neutral`) won ~40 inputs simply because the
generic tokens **modern** and **clean** appear in almost every product mood and in the generic
keyword sets. Per-corpus IDF collapses those high-frequency tokens toward weight 1.0 and lets
each product's **own specific mood** win. Examples (all clear improvements):

| Input | old -> new | Why better |
|---|---|---|
| `restaurant` (warm;appetite) | modern-neutral -> **warm-humanist** | "modern" no longer outweighs the rare, on-brand "warm"; warm-humanist (Fraunces/Nunito Sans) is the warm pairing |
| `ecommerce-store` (clean;friendly) | modern-neutral -> **friendly-rounded** | "friendly" (specific) beats the generic "clean"; soft-ui store gets a rounded, friendly face |
| `nonprofit` / `travel-tourism` (warm;...) | modern-neutral -> **warm-humanist** | same IDF effect; the product's "warm" carries the pick |
| `blog-publisher` (literary;readable) | modern-neutral -> **editorial-classic** | editorial-classic mood is `sophisticated;literary` — the literal mood match now wins |
| `product-detail-page` / `saas-landing` (clean;modern) | modern-neutral -> **clean-geometric** | "clean" matches clean-geometric's NAME field (high weight); Manrope is a clean geometric SaaS face |

### The difflib fuzzy pass connects product/industry words to font `best_for`
| Input | old -> new | Why better |
|---|---|---|
| `agency-portfolio` (precise;bold) | tech-precise -> **swiss-objective** | tech-precise only tied on "precise" and won on CSV order. swiss-objective is mood `objective;precise` for best_for `agencies;portfolios` — "portfolio" ~ "portfolios" fuzzy-matches. The intended agency face. |
| `mobile-app-landing` (modern;energetic) | bold-startup -> **clean-geometric** | clean-geometric best_for `saas;mobile-apps` — "mobile-app" matches "mobile" exactly + "app"~"apps"; clean-geometric is "excellent at small sizes" (mobile) |
| `developer-tool` modern-minimal | tech-precise -> **minimal-mono** | minimal-mono (Space Mono, best_for `developer-tools;portfolios`) matches both the code-forward intent and the explicit "minimal" keyword |

### The 2 palette changes — IDF beats a generic keyword
| Input | old -> new | Why better |
|---|---|---|
| `personal-brand` bold-premium | creative-bold-magenta -> **media-editorial-ink** | product palette_mood is `editorial-ink`; under raw overlap "bold"+"creative" tied editorial+ink and CSV order won. IDF makes the rarer, on-mood `editorial-ink` palette win — the literal mood the product asked for. |
| `portfolio-photographer` bold-premium | creative-bold-magenta -> **media-editorial-ink** | same: palette_mood `editorial-ink` now wins over a generic "bold,premium" overlap |

### Explicit-keyword responsiveness (only the keyworded set changed; defaults preserved)
`healthcare-practice` and `wellness-spa` change **only** in the `bold-premium` set
(-> bold-startup): the user explicitly asked for "bold", which the old ranker ignored. Their
`default`/`own-mood` picks are unchanged. This is the engine correctly honoring stated intent.

## Flagged for reviewer judgement (lateral, not clearly better)
- **`automotive` default/own-mood: tech-precise -> bold-startup.** Product mood is `bold;sharp`
  with a `dark-tech` style. The new ranker prefers bold-startup because "bold" (the product's
  first-listed mood) hits the high-weight NAME field; the old tech-precise matched "sharp".
  Both are defensible for automotive; a reviewer may prefer tech-precise's technical edge for a
  dark-tech aesthetic. Not a wrong/generic pick, but the one change I would not call a strict
  improvement. (To revert just this lane behavior, flip `DPS_RANKER=legacy`.)

All other 65 changes are improvements or on-brand laterals; **no change produces a generic or
off-brand pairing**, and every changed input still returns a sensible font/palette for the product.
