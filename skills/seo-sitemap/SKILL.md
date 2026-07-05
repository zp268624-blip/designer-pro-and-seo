---
name: seo-sitemap
description: Audits and generates sitemaps.org-compliant XML sitemaps. Validates structure (well-formed XML, the 50,000-URL / 50 MB limits, absolute URLs) and flags sampled URLs that 404, are noindexed, or canonicalize elsewhere; splits into a sitemap index automatically past 50,000 URLs. Trigger when the user says "sitemap", "XML sitemap", "generate sitemap", "validate sitemap", "sitemap issues", or "sitemap index".
---

# seo-sitemap

**Family:** seo
**Status:** Stable

## Purpose

Audit and generation for XML sitemaps. The script handles structure deterministically
(well-formed XML, the 50,000-URL / 50 MB protocol limits, automatic sitemap-index
splitting, absolute-URL checks); the skill layers the live quality gates that catch
the most common silent issues: URLs that 404, are noindexed, or canonicalize
elsewhere should never be in a sitemap.

## Triggers

- "sitemap" / "xml sitemap"
- "generate sitemap" / "sitemap index"
- "sitemap issues"

## Inputs

- A sitemap file/URL (audit), or a list of URLs (generate)
- Optional: base URL (for index child links) and a lastmod date

## Steps

1. **Validate structure:**
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/sitemap_tools.py" --validate sitemap.xml
   ```
   Checks well-formedness, root type (urlset vs sitemapindex), URL count vs the
   50,000 limit, file size vs 50 MB, and that every `<loc>` is absolute http(s).
2. **Apply the live quality gates** (the high-value part): for a sample of the
   sitemap's URLs, confirm via `seo-page`/fetch that each returns 200, is **not**
   noindexed, and does **not** canonicalize to a different URL. Flag any that fail —
   these silently waste crawl budget.
3. **Generate** a fresh sitemap from a URL list when needed:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/sitemap_tools.py" --generate --urls urls.txt --out sitemap.xml \
     --base-url https://site.com --lastmod 2026-06-01
   ```
   It splits into a sitemap index automatically past 50,000 URLs.
4. **Lastmod discipline:** set `lastmod` from real content-change dates, not
   auto-bumped to today on every regen (Google learns to distrust it otherwise).
5. **Robots:** confirm `robots.txt` has a `Sitemap:` directive pointing to it.

## Capability routing

This skill follows the plugin's capability-tier cascade
(`references/CAPABILITY-TIERS.md`) and always produces a validated sitemap:

1. **Tier 1 — Firecrawl MCP.** When connected, crawl the live site to discover the
   true URL set (including JS-only pages) before validating or generating.
2. **Tier 2 — built-in (the default).** Otherwise `sitemap_tools.py` validates
   structure deterministically and generates a sitemaps.org-compliant file from a
   URL list, with `site_map.py` supplying the robots + sitemap-recursion inventory.
   Fully offline — this is the product.
3. **Tier 4 — guided.** If the URL set must come from a JS-rendered crawl and
   Firecrawl isn't connected, deliver the structural validation + generation and
   name what a full crawl would add.

```capability-routing
capability:   site-map
tier1:        Firecrawl MCP
tier1_signal: FIRECRAWL_API_KEY | FIRECRAWL_API_URL
tier2:        sitemap_tools.py (validate + generate, sitemaps.org limits) + site_map.py (robots + sitemap recursion -> URL inventory)
tier2_yields: validated sitemaps.org-compliant sitemap + 404/noindex/canonical offender list, zero spend
tier3:        none
tier3_signal: none
tier4:        paste the sitemap or URL list; add a Firecrawl MCP to discover JS-only URLs for a full inventory
needs_tier1:  none
```

Always end by stating which tier ran and what a full crawl would add.

## Outputs

- Structure validation report
- Quality-gate results (404 / noindex / canonical-elsewhere offenders)
- Generated sitemap(s) + index for large sites

## Dependencies

- `scripts/seo/sitemap_tools.py` (required) — Python 3.10+, standard library only
- `seo-page` (optional — for the per-URL live quality gates)

## Notes

The "no noindex, no canonical-elsewhere" gates catch the most common silent sitemap
issue. Structure is validated offline; the live gates need URL fetches.
