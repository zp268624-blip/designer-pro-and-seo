# seo-audit — the health-score model (scoring weights)

Knowledge the `seo-audit` orchestrator loads on demand to turn a variable set of
specialist scores into one honest health score. The **implementation** is
`scripts/workflow/audit_aggregate.py`; this file is the rationale and the weight
table it applies. Knowledge, not steps — the procedure lives in
`skills/seo-audit/SKILL.md`.

## The model: a re-normalized weighted average

`seo-audit` is a socket: it dispatches whichever specialists apply (five always-on,
plus the conditional ones the business type and connected tooling call for — see
`dispatch-matrix.md`). A **fixed-denominator** average would silently punish a site
every time a specialist was *skipped*: not running `seo-ecommerce` on a law firm, or
`seo-backlinks` with no backlink source connected, would drag an otherwise-healthy
score toward zero for work that was never in scope.

So the score is **re-normalized over the specialists that actually ran**:

```
overall = sum(weight_i * score_i) / sum(weight_i)      over present specialists only
```

A skipped specialist is **excluded from the denominator** — it neither helps nor
hurts. The score reflects exactly the work that was done, and the breakdown names
every specialist that contributed and its normalized weight.

## The weight table

Higher weight = larger contribution **when that specialist is present**. The table is
this plugin's own — chosen so the two universal on-page pillars (the per-URL review
and the technical spine) anchor the score, structured/media/architecture checks form
the middle band, and AI-citability rides as a lighter modifier. Any specialist not
listed contributes at the default weight.

| Specialist | Weight | Band |
|---|---|---|
| `seo-technical` | 20 | anchor — the technical spine |
| `seo-page` | 20 | anchor — per-URL on-page review |
| `seo-content` | 15 | content depth / E-E-A-T |
| `seo-schema` | 10 | structured data |
| `seo-sitemap` | 10 | crawl architecture |
| `seo-image-audit` | 10 | media SEO |
| `seo-local-unified` | 10 | local (when applicable) |
| `seo-ecommerce` | 10 | store (when applicable) |
| `seo-google` | 10 | field data (when connected) |
| `seo-backlinks` | 10 | off-page (when connected) |
| `seo-geo` | 5 | AI-citability modifier |
| *(any other specialist)* | 10 | default weight |

These weights are the `DEFAULT_WEIGHTS` table in `audit_aggregate.py`; keep the two in
sync. They are **not** derived from any third-party audit's category split — the
count, the bands, and the numbers come from this plugin's own specialist set.

## Grade bands

The overall 0–100 score maps to a letter for at-a-glance reporting:

| Score | Grade |
|---|---|
| 90–100 | A |
| 80–89 | B |
| 70–79 | C |
| 60–69 | D |
| < 60 | F |

## Honesty rules the score obeys

- **Connector-gated depth is never folded in as a fabricated value.** A specialist
  that depends on a connector (e.g. `seo-google` field CWV, `seo-backlinks` referring
  domains) contributes only its **free-path** score; the connector-only depth is
  carried forward as `needs_tier1`, not invented.
- **Never report a complete score when a heavy category was connector-gated and
  skipped.** State which specialists ran on the free path and which are partial or
  absent — the re-normalization note plus the `specialists_present` list keep the
  headline number honest.
- **A skipped specialist is disclosed, not hidden.** The "covered / not covered" list
  in the audit output names every specialist that did not run and why.

## Worked example

Suppose only three specialists run — `seo-technical` (score 80, weight 20),
`seo-page` (90, 20), and `seo-schema` (70, 10). Total weight = 50.

```
overall = (20*80 + 20*90 + 10*70) / 50
        = (1600 + 1800 + 700) / 50
        = 4100 / 50
        = 82.0   -> grade B
```

`seo-ecommerce`, `seo-backlinks`, and the rest are simply absent from the
denominator — the site is graded on the audit that was actually performed, and the
breakdown shows the three contributors and their normalized weights (0.4 / 0.4 / 0.2).
