# Produce · Ship the schema and indexation deliverables

**Loop stage:** Produce — the structured-data and discoverability layer each page ships with.
**When to run:** with every page produced, before it goes live.

A page is not "produced" until search engines and AI answerers can parse and find it.
This prompt generates and validates the structured data and updates the sitemap, so the
page ships discoverable — and so the schema becomes a drift-tracked element Verify watches.

## Evidence to gather (free Tier-2)

- `scripts/seo/schema_gen.py` — generates and validates Schema.org JSON-LD against
  Google's rich-result required/recommended properties, per vertical (e.g. per-vertical
  `LocalBusiness`, `Product`/`Offer`, `Article`, `FAQPage` — encoding the 2026 FAQPage
  rich-result narrowing). See `references/shared/schema-catalog.md`.
- `scripts/seo/sitemap_tools.py` — generates/validates a sitemaps.org-compliant sitemap,
  enforcing the 50,000-URL / 50 MB protocol limits, so a new page is actually submitted.

`needs_tier1`: whether a rich result is *granted* is a never-fabricate field — validate
against the spec (eligibility), and mark actual rich-result appearance as connector/GSC-read.

## The prompt

> Produce the schema and indexation deliverables for {this page}. Generate the JSON-LD for
> the page's type, validate it against the required and recommended properties, and report
> any missing required property as a build blocker (not a warning). Choose the schema type
> from the vertical template (`LocalBusiness` for local, `Product`/`Offer` for ecommerce,
> `Article` for publisher, etc.). Add the new URL to the sitemap and validate it stays
> within protocol limits. Confirm `schema_blocks` will now register in the drift snapshot
> so Verify can watch it. Validate eligibility only; mark granted rich results as
> connector-read under `needs_tier1`.

## Decision it drives

- **The structured-data and sitemap deliverables** that ship with each page, and any
  missing-required-property **build blocker** to fix before launch.

## Hand off to

- `verify/01-baseline-diff.md` — `schema_blocks` and `canonical` are drift-tracked; the
  next snapshot proves they landed.
- `design-build` — the validated JSON-LD is embedded at build time.
