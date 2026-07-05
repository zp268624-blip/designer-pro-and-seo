# Golden example — seo-sitemap (Tier-2: `sitemap_tools.py`)

Proves the **free Tier-2** path of `seo-sitemap` validates a sitemap
deterministically with no network and no API key — the `site-map` capability's
built-in product. Reproducible offline.

## Input

- `sample-sitemap.xml` — a small, well-formed `urlset` with three absolute-URL
  entries and `lastmod` dates.

## Commands

Both halves of the Tier-2 contract run offline against the sample, with no network and
no API key.

**1 — structure validation (`sitemap_tools.py`):**

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/sitemap_tools.py" \
  --validate references/examples/seo-sitemap/sample-sitemap.xml
```

**2 — robots + sitemap-recursion URL inventory (`site_map.py`):**

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/site_map.py" \
  --file references/examples/seo-sitemap/sample-sitemap.xml --no-network --human
```

(From the repo root during development, drop `${CLAUDE_PLUGIN_ROOT}/` and run the
bare `scripts/...` path.)

## Expected free deliverable (Tier 2)

A structural validation report (JSON), e.g.:

```
{
  "action": "validate",
  "root": "urlset",
  "valid": true,
  "errors": [],
  "warnings": [],
  "url_count": 3
}
```

It confirms well-formedness, root type (`urlset` vs `sitemapindex`), the
50,000-URL / 50 MB protocol limits, and that every `<loc>` is absolute http(s).

`site_map.py` (command 2) extends the same Tier-2 with a robots + sitemap-recursion
URL inventory, e.g.:

```
# SITEMAP / URL INVENTORY: references/examples/seo-sitemap/sample-sitemap.xml
mode=offline-file  source=sitemap  base=https://example.test/
counts: total=3 internal=3 external=0 disallowed=0
by page-type: home=1, page=2
```

No Tier-1 connector is required (`needs_tier1: none`); Firecrawl only adds JS-only
URL discovery (Tier 1).
