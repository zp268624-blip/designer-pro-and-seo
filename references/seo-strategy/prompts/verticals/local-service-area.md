# Vertical template · Local & service-area business

**Covers `business_type.py` output:** `local` (LocalBusiness schema, physical address/NAP,
storefront language, location pages) **and** `sab` (service-area language, "areas we
serve", free-estimate CTAs, service-business schema). Collapsed into one template because
both run the same local toolchain.
**Center of gravity:** Google Business Profile, NAP consistency, location/service-area
pages, Share-of-Local-Voice geo-grid, review signals.

A strategic **tilt** applied over the six-stage loop.

## What wins here

Local rankings are won in the map pack, not just the blue links, and the levers are
consistency and proximity: a clean NAP across listings, complete location or service-area
pages, and review velocity. The winnable territory is geographic — the same service across
each served location — so the geo-grid, not a national keyword list, is the truth signal.

## Per-stage tilt

- **Baseline** — expect few but high-value location/service pages. Run `nap_check.py` early:
  NAP inconsistency across listings is a silent, common drag.
- **Diagnose** — weight **LocalBusiness schema, NAP consistency, and location-page
  completeness up**. GEO/citability matters for "near me" answers, but proximity dominates.
- **Cluster** — cluster around "{service} {city}" and "{service} near me"; each served
  location is a spoke pattern, not a separate topic. Avoid spinning thin doorway pages —
  each location page must earn distinct content.
- **Prioritize** — weight **local-pack levers up**: GBP completeness, NAP fixes, and review
  strategy usually outrank net-new blog content for a local business's near-term revenue.
- **Produce** — schema is per-vertical `LocalBusiness`; briefs enforce genuinely distinct
  location-page content; hand map-pack and review work to `seo-local-unified`.
- **Verify** — run `geogrid.py` for Share-of-Local-Voice across the served grid each cycle;
  drift watches NAP/schema on location pages; GBP insights and call volume are `needs_tier1`.

## Scripts that matter most

`business_type.py` (confirm local/sab + vertical) -> `nap_check.py` (consistency) ->
`geogrid.py` (SoLV across the grid) -> `schema_gen.py` (LocalBusiness).

## Money vs authority

Money = GBP + location/service-area pages + reviews. Authority = local topical content
("{service} guide for {region}"). Fix NAP and GBP first; measure with the geo-grid, not a
national rank.
