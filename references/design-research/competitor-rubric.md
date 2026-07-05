# Competitor scoring rubric — how to apply it

Durable knowledge for turning a competitive scan into a *comparable*, defensible
score. The rubric itself lives in `data/competitor-rubric.csv`; this file is the
method that keeps every competitor scored the same way, so the numbers in
`research/02-competitor-analysis.md` mean something.

Use this when scoring the target and each competitor in `design-research` step 5.
It is knowledge, not procedure — the ordered steps stay in the SKILL body.

## What the rubric is

`data/competitor-rubric.csv` holds **18 scoring dimensions** grouped into six
categories that a design-research pass actually judges:

| category | what it measures | dimensions |
|---|---|---|
| `positioning` | does the site say who it is for and why it wins | value-prop clarity, audience specificity, differentiation |
| `brand-craft` | does it look intentional rather than templated | visual hierarchy, typographic system, color discipline |
| `content-depth` | does it prove its claims and stay findable | proof/specificity, freshness, information scent |
| `trust-signals` | would a stranger believe it | social proof, credibility markers, transparency |
| `conversion-path` | is acting easy and obvious | primary-CTA clarity, friction/form load, mobile readiness |
| `findability` | can search and AI surface it | on-page SEO surface, metadata/schema, performance signals |

Each row carries a `weight` (its contribution to the composite), a
`what_good_looks_like` anchor, a `what_bad_looks_like` anchor, a
`signal_to_check` (the observable evidence to fetch or inspect), and a
`white_space_test` (the condition under which the whole competitor set is weak on
that dimension — the seam `design-research` exists to find).

## The scoring scale (fixed, so scores compare)

Score every dimension **0–4** against the two anchors, never on vibes:

- **4** — clearly matches `what_good_looks_like`; a reference example.
- **3** — mostly good; one minor gap.
- **2** — mixed; the good and bad anchors both partly apply.
- **1** — mostly matches `what_bad_looks_like`.
- **0** — fully the bad anchor, or the signal is absent entirely.

The anchors are the whole point: a 4 and a 1 must be defensible by pointing at the
`signal_to_check`, not by taste. If two reviewers can't agree within one point,
the anchor is being read loosely — re-read the `signal_to_check` cell.

## The composite (weighted, normalized)

A competitor's category score is the weighted mean of its dimensions:

```
category_score = sum(weight_i * score_i) / sum(weight_i)   # over rows in that category, 0..4
overall        = sum(weight_i * score_i) / sum(weight_i)   # over all 18 rows, 0..4
```

Report the six category scores **and** the overall on the same 0–4 scale so a radar
or bar chart reads honestly. Do **not** rescale to 100 and imply precision the
0–4 judgement doesn't have. Weights are deliberately uneven — `value-proposition-
clarity` and `primary-cta-clarity` carry 5 because a site that fails them fails
commercially regardless of craft; `content-freshness` and `metadata-and-schema`
carry 2 because they are real but rarely decisive. The weights are the plugin's
own editorial priority, not a borrowed scheme; adjust them per engagement only with
a note in the report.

## Reading the `white_space_test` column (the differentiator)

White space is not "who scores lowest" — it is **a dimension where the entire set is
weak at once**. After scoring, walk each dimension across all competitors:

- If *every* competitor scores ≤ 2 on a dimension and its `white_space_test`
  condition holds, that dimension is an **open lane** — flag it in
  `research/03-build-brief.md` as something the build can own cheaply.
- If one competitor scores 4 and the rest score low, that is a **moat to respect**,
  not white space — note it as table stakes to match, not a lane to claim.
- Weight the lane by the dimension's `weight`: an open `conversion-path` lane
  (weight 4–5) is worth more than an open `content-freshness` lane (weight 2).

This is the hand-off into the design and SEO work: the highest-weight open lanes
become the brief's headline moves.

## Worked example (fictional)

Scoring three competitors for a project-management SaaS brief:

- `zephyr-pm.example` — value-prop 4, differentiation 2, primary-CTA 4,
  transparency 1 (pricing hidden behind a demo gate).
- `orbit-tasks.example` — value-prop 2 (hero says only "Work, better"),
  differentiation 1, primary-CTA 3, transparency 1.
- `northwind-plan.example` — value-prop 3, differentiation 2, primary-CTA 2
  (four equal buttons), transparency 1.

`transparency` scores 1 across all three and the `white_space_test` ("the niche
hides pricing so openness becomes a wedge") holds — an **open lane** at weight 3.
`differentiation-vs-category` is weak across the set too (weight 4) — a higher-value
lane. `value-proposition-clarity` has one strong incumbent (`zephyr-pm.example` at
4), so it is table stakes, not white space. The brief leads with a differentiated,
transparently-priced value prop — the two highest-weight open lanes, evidenced, not
guessed.

## Honesty rules

- A dimension you could not observe (the signal wasn't fetchable — JS-gated,
  auth-walled) is scored **absent**, not zero, and listed under "not assessed —
  Tier-1 crawl would resolve." Never infer a score from nothing.
- Never fabricate a competitor's SEO/performance number to fill `findability`;
  score only the on-page signals you actually inspected and label the rest as
  needing a live crawl or field data.
- Keep the same reviewer (or the same anchors) across all competitors in one
  engagement; a rubric only compares if it is applied identically.

## Related

- `references/design-research/white-space-method.md` — the first-principles method
  behind the `white_space_test` column and the whitespace/rhythm read of
  `visual-hierarchy`.
- `data/competitor-rubric.csv` — the rubric rows this file scores against.
