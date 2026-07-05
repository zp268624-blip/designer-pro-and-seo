# E-E-A-T — Checkable Quality Criteria

Shared reference for the content-quality skills (`seo-content`,
`seo-content-brief`, `seo-geo`, `seo-page`, `seo-audit`). E-E-A-T —
**Experience, Expertise, Authoritativeness, Trust** — is Google's public framing
of the qualities that signal page and site quality, with **Trust** as the
foundation the other three support. It is a *concept*, not a ranking dial; this
file restates it as original, checkable criteria the plugin can score against.
Knowledge, not steps.

## The four pillars (with Trust at the center)

- **Experience** — was the content produced by someone with first-hand,
  lived contact with the subject (used the product, visited the place, did the
  procedure)? First-hand experience is hard to fake and increasingly the
  differentiator on commodity topics.
- **Expertise** — does the author have the relevant skill or knowledge for the
  topic? The bar is topic-relative: a hobbyist's deep specialty can outrank a
  generalist; medical/financial/legal topics demand formal credentials.
- **Authoritativeness** — is the author or site a recognized go-to source on this
  topic, as evidenced by citations, mentions, and reputation *off* the page?
- **Trust** — is the page accurate, honest, safe, and transparent about who is
  responsible for it? Everything else is in service of trust; an untrustworthy
  page is low quality however expert it appears.

## YMYL raises the bar

For **Your Money or Your Life** topics — health, finance, safety, legal, major
life decisions — the consequences of bad information are severe, so the evidence
of Experience/Expertise/Authoritativeness/Trust must be correspondingly stronger.
The plugin weights YMYL pages harder on author credentials, sourcing, and
accuracy.

## Checkable criteria (what the plugin actually inspects)

### Trust signals
- Author is named and identifiable (not "admin" / no byline).
- Clear contact information and a real organizational identity.
- Visible publish date and a meaningful last-updated date.
- Claims are sourced; statistics cite a primary origin.
- No deceptive patterns: ads distinguishable from content, no cloaked affiliate
  intent, no fabricated reviews or ratings.
- Secure, error-free, and honest about limitations or sponsorship.

### Experience signals
- First-hand markers: original photography, specific anecdotes, "we tested,"
  measured results, lived detail a researcher could not invent.
- Specificity over generality — concrete numbers, named conditions, edge cases.

### Expertise signals
- Author bio establishing relevant background; credentials shown for YMYL.
- Correct, current terminology; absence of factual errors a specialist would
  catch.
- Depth that answers the follow-up questions, not just the headline query.

### Authoritativeness signals
- Cited or referenced by other reputable sources in the niche.
- Consistent identity across the web (the site/author is "the" source people
  name).
- Original research, data, or tools others link to.

## Relationship to AI answer engines (GEO)

The same qualities that signal E-E-A-T to a search ranker also make a passage
**citable** by AI answer engines: a clearly-attributed, well-sourced, specific,
self-contained statement is both trustworthy and easy to lift as a citation. The
plugin treats strong E-E-A-T as a prerequisite for GEO citability rather than a
separate exercise.

## Scoring stance (free-path note)

E-E-A-T cannot be read from an API; it is assessed by inspecting the page's own
signals against the criteria above. The plugin scores these deterministically
from the page HTML and content (byline present?, dates present?, sources
linked?, first-hand markers?) and reports a rubric, never a single opaque
"E-E-A-T score" presented as Google's own. It is a diagnostic of observable
quality signals, honestly labeled.
