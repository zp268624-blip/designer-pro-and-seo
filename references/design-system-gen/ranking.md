# The design ranker — weighted-IDF matching (our own algorithm)

Durable knowledge for `design-system-gen`: *how* the engine chooses a style,
palette, typography pairing, and product row from the CSV libraries, and *why* the
scoring is shaped the way it is. This is the reasoning behind `scripts/design/match.py`
(the ranker) and its four callers in `scripts/design/design_system.py`
(`pick_product` / `pick_style` / `pick_palette` / `pick_typography`) — not a
procedure. The steps of running the engine live in the SKILL body.

Every weight and constant below is original, authored from first principles for this
plugin's own CSV schema and tuned on its own corpus.

## The problem this fixes — generic-token bias

The first-generation picker scored a row by **raw token overlap**: count how many
query tokens appear in the row's fields, highest count wins. That rewards rows that
mention *common* words. A keyword set like `modern, minimal, clean` overlaps almost
every row, because "modern" and "clean" appear everywhere in a style library — so the
distinctive token in the query (`brutalist`, `editorial`, `luxury`) gets outvoted by a
pile of generic matches. The ranker's whole job is to make the **rare, specific** token
decide the match while the generic tokens fade to near-zero influence.

## The scoring model

For a candidate row, given the query token set and a per-picker list of
`(field, weight)` pairs:

```
score(row) = ( SUM over query tokens qt of contribution(qt, row) ) / lnorm(row)
             + domain_adjust(row)     # optional tie-break bonus/penalty
```

Five ideas combine to produce `contribution`, `lnorm`, and the honesty flags.

### 1. Per-corpus IDF — the core fix

Each row is treated as one "document": the union of the tokens across its weighted
fields. A token's **document frequency** `df` is how many rows contain it, over `N`
rows. Each matched token is weighted by a smoothed inverse-document-frequency:

```
idf(t) = ln( (N + 1) / (df + 1) ) + 1.0
```

The smoothing (`+1` top and bottom, `+1.0` floor) guarantees `idf(t) >= 1.0`, so a
token that appears in **every** row still counts — just barely (it collapses to ~1.0).
A token that appears in **one** row earns the maximum idf. That is the mechanism that
lets `brutalist` (rare) outweigh `modern` (in most rows): they are not counted equally.

### 2. Field weights — one contribution per query token

Not every field is equally identifying. A match on a row's **name/identity** field
means more than a match buried in long prose. Each picker passes its own weight ladder
(heaviest → lightest):

| Picker | Ladder (field : weight) |
|---|---|
| product | `product_type` 3.0 · `industry` 2.0 · `recommended_style` 1.5 · `key_sections` 1.0 · `notes` 0.8 |
| style | `style` 3.0 · `mood_tags` 2.0 · `best_for` 1.5 · `characteristics` 1.0 · `summary` 0.8 |
| palette | `name` 2.5 · `mood` 2.0 · `industry` 2.0 · `tags` 1.2 |
| typography | `name` 2.5 · `mood` 2.0 · `best_for` 1.5 |

A query token's contribution uses the **single highest-weighted field it appears in** —
never summed across fields. So a token repeated across a row's `style`, `mood_tags`, and
`summary` cannot inflate the score three times; it counts once, at its best field:

```
contribution(qt, row) = idf(matched_token) * max_field_weight(qt, row) * quality
```

`quality` is `1.0` for an exact field match, or the fuzzy ratio (below) for a near-miss.

### 3. difflib fuzzy pass — near-misses without a synonym table

When a query token is not an exact member of a field's tokens, the ranker takes the
best `difflib` ratio against that field's tokens. A ratio `>= 0.82` (FUZZY_THRESHOLD)
counts as a discounted match: `quality = ratio`, scored with the *matched corpus
token's* idf. This handles morphology and typos with zero maintenance —
`minimalist ~ minimal`, `portfolio ~ portfolios` — no hand-built synonym list. Ratio
ties break on the lexically-smallest token so the chosen idf (and the result) is
deterministic regardless of set ordering.

### 4. Pivoted length normalization — verbose rows don't win by bulk

A row with more text has more chances to match. To stop a verbose row from beating a
focused one on volume alone, the summed contribution is divided by a pivoted-length
factor:

```
lnorm(row) = (1 - B) + B * ( doc_len(row) / avg_doc_len )      B = 0.25
```

At `B = 0.25` a row of average length is unchanged (factor 1.0); a longer-than-average
row is mildly damped; a short, focused row gets a small lift. `B = 0` would disable
normalization entirely; `B = 1` would fully divide by length. The mild value keeps the
IDF signal dominant while removing the worst of the length bias.

### 5. Honesty — confidence floor and tie margin

The ranker never pretends a weak match is strong:

- **CONFIDENCE_FLOOR = 1.5.** If the best score is below the floor, no field carried a
  real specific match; the dimension is reported as a weak match (`matched = False`),
  the *closest* row is still returned, and `design_system.py` records it in
  `_fallbacks` ("no strong match — returned closest; refine keywords"). The floor sits
  **above** any domain tie-break bonus, so a bonus alone can never lift a no-match row
  over the floor.
- **TIE_MARGIN = 0.05.** If a runner-up's score is within 5% (relative) of the winner,
  the pick is flagged `ambiguous`, so the engine can disclose that the top candidates
  were close (the deterministic winner is still returned).

### The domain adjust hook

Two callers pass an `adjust(row, score)` for a domain tie-break, applied **after**
length normalization and kept smaller than the floor so it can only break ties, never
manufacture a match:

- **palette** adds `AA_BONUS = 0.5` when the row's `aa_body_text == "pass"` — a
  WCAG-AA-safe palette edges out an equal-scoring one.
- **style** subtracts `AVOID_PENALTY = 2.0` when a query token appears in the row's
  `avoid_for` field — a style that explicitly warns against the requested use is damped.

## Determinism (a hard contract)

Same input → byte-identical output. Rows are scored in CSV order; the winner updates
only on a **strictly greater** score, so exact ties resolve to the earliest (lowest-
index) row. Query tokens are sorted before summation so float addition order is fixed
run to run. There is no randomness and no dict-ordering dependence. `match.py` ships
behind the `DPS_RANKER` flag (`new` default, `legacy` revert path); `legacy` reproduces
the pre-ranker golden baseline exactly.

## Worked example A — the generic-token trap

Style query `modern, minimal, brutalist` against a 3-row toy corpus. Assume `modern`
and `minimal` appear in all 3 rows (df = 3, idf ≈ 1.0) and `brutalist` appears in one
row's `style` field (df = 1, idf ≈ ln(4/2)+1 ≈ 1.69).

- **Raw overlap** would score the two generic rows at 2 (they match `modern` +
  `minimal`) and the brutalist row at 3 — close, and easily flipped by one extra
  generic word elsewhere.
- **Weighted-IDF:** the brutalist row earns `1.69 (idf) * 3.0 (style field) = 5.07`
  from that one token *plus* its generic matches; the generic rows earn only
  `~1.0 * (mid-weight field)` per token. The specific token dominates by design, and
  the correct row wins with margin — not by a fragile one-point lead.

## Worked example B — floor and fuzzy together

Palette query `calm, trustworthy` against a corpus where no row's `name`/`mood`/
`industry`/`tags` contains either token exactly, but one row's `mood` is `serene` and
`trust`. `serene` is not an exact hit for `calm`, and difflib rates them below 0.82 — no
match there. `trust ~ trustworthy` scores a difflib ratio around 0.67 — also below
threshold — so neither token lands a real hit. The best score stays under 1.5, the
dimension is flagged `matched = False`, the closest row is returned, and the engine
writes a `_fallbacks` line telling the user to refine keywords. The ranker declined to
fake confidence — the honest outcome, and exactly what the floor is for.

## See also

- `scripts/design/match.py` — the implementation these notes describe.
- `scripts/design/design_system.py` — the four pickers and their weight ladders.
- `references/shared/wcag-contrast-rules.md` — the AA logic behind the palette bonus.
