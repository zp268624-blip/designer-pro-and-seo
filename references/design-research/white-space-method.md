# White-space & rhythm — a first-principles method

Durable knowledge for reading the *negative space* of a page: the spacing, density,
and rhythm that make a competitor's site feel intentional or amateur. This is the
craft lens behind the `visual-hierarchy`, `typographic-system`, and
`color-system-discipline` rows of `data/competitor-rubric.csv`, and behind the
"does it look designed or templated" judgement in `design-research`.

Two different things share the word "white space." This file is about **literal
negative space** — the emptiness between and around elements. The *competitive*
white space (unfilled market lanes) is the `white_space_test` column, covered in
`references/design-research/competitor-rubric.md`. Read them together; do not
conflate them.

## First principle: space is a decision, not a leftover

Amateur layouts treat empty pixels as waste to be filled; designed layouts spend
space deliberately to create grouping, hierarchy, and calm. So the diagnostic
question is never "is there enough white space" — it is **"is the space
intentional and consistent?"** A cramped page and a page with random huge gaps both
fail the same test: the spacing carries no meaning.

Three forces produce good negative space:

1. **Proximity** — related things sit closer than unrelated things. Space *is* the
   grouping mechanism; a label glued to the wrong field reads as a different group.
2. **Consistency** — the gaps come from a small repeated scale, not ad-hoc numbers.
   The eye reads a rhythm; it notices when the rhythm breaks even if it can't name why.
3. **Breathing room at the edges** — content is not jammed against the viewport or
   its container; padding signals confidence.

## The spacing-scale test (consistency)

Intentional designs draw every gap from a **small geometric-ish scale** (e.g. a base
step doubling-ish: 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64). This is the same lineage as
this plugin's own token scale in `render_page.py` — spacing is emitted from a fixed
step set, never freehand.

To evaluate a competitor:

- Sample the vertical gaps between major sections and the padding inside cards and
  buttons (measure in the browser or read the CSS if fetchable).
- **Count the distinct values.** A confident system uses roughly **4–7 distinct
  spacing values** across the whole page. Twelve-plus distinct near-but-not-equal
  gaps (17px here, 19px there, 22px next) is the signature of freehand,
  un-systematized spacing — score `visual-hierarchy` and craft down.
- **Check the ratio.** Adjacent steps in a good scale sit in a consistent ratio
  (roughly 1.4–2.0×). A scale that jumps 8 → 10 → 40 has no rhythm.

## The vertical-rhythm test (typography)

Rhythm is spacing applied down the page. Good body typography sits on a consistent
vertical beat: line-height, paragraph spacing, and the space above headings are all
multiples of one base unit, so text feels like it has a pulse.

- **Line length (measure).** Comfortable reading is ~45–75 characters per line.
  Full-viewport-width paragraphs (100+ chars) and cramped 30-char columns both break
  rhythm and readability — a fast tell of an unconsidered layout.
- **Line-height.** Body copy near 1.4–1.6× the font size reads calmly; 1.0–1.2×
  (default-ish) feels dense and un-designed.
- **Heading air.** Space *above* a heading should exceed space below it, so the
  heading binds to the content it introduces (proximity again). Equal or inverted
  spacing makes headings float.

## The density-and-balance read (holistic)

Step back and squint at a screenshot until the text blurs. You are now reading pure
mass and void:

- **Even density?** A well-composed screen distributes mass without one corner
  going heavy and another going empty. A giant empty right rail beside a crammed left
  column reads as broken, not spacious.
- **Aligned voids?** Negative space should have clean edges — content aligns to a
  grid so the gaps between blocks line up. Ragged, misaligned gutters read as
  accidental even when generous.
- **Figure/ground clarity?** The primary action and headline should sit in the most
  open region so space *points* at them. If the busiest, tightest area is where the
  CTA lives, the space is fighting the hierarchy.

## Scoring hook (how this feeds the rubric)

- Consistent small scale + comfortable measure + heading air + even density →
  `visual-hierarchy` and `typographic-system` score high (3–4); the site reads as
  designed.
- Many ad-hoc gaps, full-width text, cramped line-height, lopsided density →
  score low (0–2); the site reads as templated regardless of its color or copy.
- When CSS/measurements aren't fetchable (JS-gated), score from the rendered
  screenshot's squint-test only and mark the precise-scale check as "not assessed —
  needs CSS access," never inferred.

## Worked example (fictional)

`meridian-studio.example` uses four spacing values (8/16/32/64), ~62-char measure,
1.5 line-height, and more air above headings than below — it squints into clean,
evenly-weighted blocks. Craft scores 4. `budget-lawns.example` mixes eleven
near-equal gaps, runs paragraphs the full 1280px width at 1.2 line-height, and
stacks a dense hero beside an empty band — it squints into lopsided mush. Craft
scores 1. The difference is not taste; it is the spacing-scale, measure, and
density tests applied identically to both.

## Related

- `references/design-research/competitor-rubric.md` — the rubric and composite this
  craft read scores into.
- `data/competitor-rubric.csv` — the `brand-craft` dimensions this method judges.
