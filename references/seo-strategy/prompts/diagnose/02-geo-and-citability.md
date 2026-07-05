# Diagnose · GEO answerability and AI-crawler policy

**Loop stage:** Diagnose — measure whether pages are retrievable and citable by AI search.
**When to run:** alongside the technical audit, on the pages meant to earn answers.

Ranking is no longer only about ten blue links. This prompt measures whether a page is
*answer-shaped* — retrievable by AI crawlers and structured so a passage can be lifted
as a citation — and turns that into concrete restructuring requirements.

## Evidence to gather (free Tier-2)

- `scripts/seo/geo_check.py` — passage-citability scoring against four axes (sourced /
  self-contained / answer-first / concise) plus an `llms.txt` + robots AI-crawler verdict
  that separates retrieval-time crawlers from training-time crawlers. It emits a `citable`
  boolean per passage and re-normalizes the scorecard over the categories actually
  available (see `references/geo-scorecard.md` for the rubric rationale).

`needs_tier1`: actual AI-answer inclusion / brand-mention share is a never-fabricate
field — the free path scores *citability readiness*, not observed inclusion; observed
inclusion is listed under `needs_tier1`.

## The prompt

> Score the GEO answerability of {the pages meant to earn AI citations}. For each page,
> report the passage-citability score on the four axes, the `citable` verdict, and the
> AI-crawler policy verdict (is a retrieval crawler allowed; is `llms.txt` present and
> coherent with robots). List the specific restructuring moves that would raise a
> non-citable passage — answer-first opening, a self-contained claim, a cited source,
> tighter length. Distinguish "we block the retrieval crawler" (a policy fix) from "the
> passage is not answer-shaped" (a content fix). Report readiness only; put observed
> AI-answer inclusion under `needs_tier1`.

## Decision it drives

- **Which pages need restructuring for citability** vs. which need a robots/`llms.txt`
  policy change — two different fixes, two different owners.
- **The citability requirements** that must be baked into every new brief.

## Hand off to

- `produce/01-brief-the-priority.md` — the citability requirements become brief constraints.
- `prioritize/01-impact-effort-intent-scoring.md` — a policy fix is usually low-effort,
  high-leverage; a restructure is scored per page.
