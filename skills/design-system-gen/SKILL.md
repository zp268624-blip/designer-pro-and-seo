---
name: design-system-gen
description: Generate a complete design system — pattern, style, color palette (with WCAG contrast), typography pairing, effects, anti-patterns, and a pre-delivery checklist — from a product type, industry, and a few style keywords. Runs fully locally from clean-room CSV libraries; no network or paid API required. Trigger when the user says "design system", "generate a design system", "pick colors and fonts for me", "what style fits a [product]", "recommend a palette for [industry]", or "give me the visual language before I build".
---

# design-system-gen

**Family:** design
**Status:** Stable

## Purpose

Produce a complete, opinionated design system in one pass. Given a product type,
target industry, and a handful of style keywords, return pattern & layout, style,
color palette (with WCAG contrast), typography pairing, effects (radius/shadow/
motion), explicit anti-patterns, and a pre-delivery checklist.

Backed by the local clean-room CSV libraries in `data/` and a deterministic
Python reasoning engine. No network or paid API required.

## Triggers

- "design system" / "generate a design system"
- "pick colors and fonts for me"
- "what style fits a [product]"
- "recommend a palette for [industry]"
- "give me the visual language before I build"

## Inputs

- Product type (e.g. "saas-landing", "restaurant", "luxury-brand") — closest match from `data/product-types.csv`
- Industry / vertical
- Style keywords (free text — "modern, minimal, dark mode")
- Output: ASCII (`--human`) for the user, or JSON when a downstream skill consumes it

## Steps

1. **Gather inputs.** Ask for (or infer) product type, industry, and 2–5 style
   keywords. If the user is vague, suggest the nearest `product_type` from
   `data/product-types.csv`.
2. **Ensure the palette library exists.** If `data/color-palettes.csv` is missing,
   generate it first (idempotent, clean-room):
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design/gen_palettes.py"    # use `py` on Windows if python3 is absent
   ```
3. **Run the engine:**
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design/design_system.py" \
     --product-type "<type>" --industry "<industry>" \
     --keywords "<comma,separated>" --human
   ```
   Drop `--human` (emit JSON) when handing the result to another skill.
4. **Read the result.** It returns pattern, style (+characteristics + what to
   avoid), palette (hex set + `text_on_bg_contrast` + `aa_body_text`), typography
   pairing (+weights + Google-Fonts availability), effects, key sections,
   anti-patterns, and the pre-delivery checklist. Note anything under `_fallbacks`.
5. **Sanity-check & adapt.** Confirm `aa_body_text` is `pass`. If keywords pulled
   an off-base style, re-run with refined keywords, or override one dimension and
   state why.
6. **Present & route.** Show the system, then offer to: persist it
   (`design-system-persist`), expand it into a brief (`design-dimensions` /
   `blast-prompt`), or emit code tokens (`design-tokens-emit`).

## Outputs

| Output | What it contains | Format | Quality bar (how it is scored) |
|---|---|---|---|
| Design system | Pattern, style (+characteristics + avoid), palette (hex + `text_on_bg_contrast` + `aa_body_text`), typography pairing (+weights + Google-Fonts availability), effects, key sections, anti-patterns | ASCII (`--human`) or engine JSON | Every dimension is a real ranked pick (see `references/design-system-gen/ranking.md`); a weak match is flagged, never faked; `aa_body_text` must be `pass` |
| Pre-delivery checklist | The design-specific checks to clear before build/handoff | ASCII / JSON list | Each item is concrete and checkable, not generic advice |
| `_fallbacks` notes | Which dimension fell back to a heuristic, was ambiguous, or was overridden by a keyword | list of one-line reasons | Present whenever a library was missing or a pick scored below the confidence floor — honesty over silent confidence |

Filed to: the user's project workspace (JSON for downstream skills; ASCII for the user).
The engine never fabricates a confident match — a below-floor pick returns the closest
row and records why in `_fallbacks`.

## Error Handling

| Condition | Detection | Behavior (degrade, never fail) | User-facing message |
|---|---|---|---|
| Palette library missing | `data/color-palettes.csv` absent | run `gen_palettes.py` once (idempotent, clean-room) then proceed | "Built the palette library first, then generated the system." |
| Any other data CSV missing | `_load` returns `None` for that library | use heuristic defaults for that dimension; record it in `_fallbacks` | "`<lib>.csv` missing — used heuristic defaults for that dimension." |
| No strong match for a dimension | best ranker score below the confidence floor | return the closest row, flag `matched = False` in `_fallbacks` | "No strong match — returned the closest; refine keywords to improve." |
| Top candidates were close | runner-up within the tie margin of the winner | return the deterministic winner, flag ambiguous | "Top matches were close — returned the highest-ranked; add a keyword to disambiguate." |
| Keyword overrode the product default | explicit style keyword names another on-file style | honor the stated intent; record the swap | "Keyword '<x>' overrode the product default '<y>' — drop it to keep the default." |
| Bad / empty input | engine validates args and exits non-zero with a JSON error | report the validation error; invent nothing | "<field> is required / unparseable — here is the expected shape." |

## Dependencies

- `scripts/design/design_system.py` (required) + the `data/*.csv` libraries
- `scripts/design/gen_palettes.py` (required once, to build the palette library)
- Python 3.10+ — standard library only, no third-party packages

## Notes

The most-invoked design skill; most other design skills call this first so all
variants share token consistency. The engine tolerates a partial data set and
flags which dimension fell back to a heuristic (see `references/ENGINE-CONTRACTS.md`).

How each dimension is chosen — the weighted-IDF ranker (per-corpus IDF + field
weights + length-norm + a `difflib` fuzzy pass + the confidence floor / tie margin
that keep it honest) — is documented in `references/design-system-gen/ranking.md`,
with worked examples of the generic-token trap it fixes.
