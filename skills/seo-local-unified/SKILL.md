---
name: seo-local-unified
description: Audits and optimizes local SEO — Google Business Profile, NAP consistency, citations, review velocity, and LocalBusiness schema. Uses DataForSEO or Google Places for maps intelligence (geo-grid rank tracking, GBP API audit, competitor radius, Share of Local Voice) when connected; otherwise delivers the full strategy, NAP matrix, and schema by hand. Trigger when the user says "local SEO", "Google Business Profile", "map pack", "NAP consistency", "citations", "geo-grid rank tracking", "multi-location SEO", or "Share of Local Voice".
---

# seo-local-unified

**Family:** seo
**Status:** Stable

## Purpose

The complete local SEO surface in one skill. Combines local strategy (GBP, NAP,
citations, reviews, schema) with maps intelligence (geo-grid tracking, GBP API,
SoLV) because they operate together. The **free path covers strategy + schema +
NAP**; the **intelligence layer is optional** (DataForSEO / Google Places).

## Triggers

- "local seo" / "local rankings" / "map pack" / "local pack"
- "google business profile" / "gbp" / "citations" / "nap consistency"
- "service area" / "multi-location"
- "geo-grid" / "rank tracking" / "review velocity" / "share of local voice" / "solv"

## Inputs

- Business name + primary address; service area or location set
- Vertical / industry
- Data tier: free (strategy+schema) | DataForSEO | DataForSEO + Google Places

## Steps

1. **GBP optimization** (free): category selection, services, attributes,
   description, photos, posts cadence, Q&A.
2. **NAP consistency** (free): confirm the exact same Name/Address/Phone format
   across the site, GBP, and major directories. Feed the citations the user lists to
   `nap_check.py`, which normalizes each NAP (so "St" vs "Street" and phone formatting
   don't false-flag) and diffs them against a canonical listing to surface the *real*
   mismatches — the silent local-ranking killer. Normalization rules + the severity
   model: `references/seo-local-unified/nap-normalization.md`.
3. **Citations & reviews** (free): identify the priority directories for the vertical;
   set a review-velocity + response plan (don't gate/buy reviews — policy risk).
4. **LocalBusiness schema** via `seo-schema`: `name` + `address` required; add
   `telephone`, `geo`, `openingHoursSpecification`; multi-location → per-location
   pages each with its own schema and a clean URL.
5. **Geo-grid / Share of Local Voice.** Local rank is geographic, so sample it on a
   lattice. `geogrid.py` builds an N×N grid around a center/address (free OSM
   Nominatim) and computes **Share of Local Voice** + coverage / top-3 / avg-rank over
   per-point rank data — fully offline once you have the ranks. The SoLV formula +
   grid math: `references/seo-local-unified/solv-geogrid-formula.md`. *Live* per-point
   ranks come from a maps connector (Tier 1) when present; otherwise the user supplies
   them (manual checks) and the math runs free.
6. **Intelligence (optional, Tier 1).** If DataForSEO/Places are configured, add live
   geo-grid rank acquisition, GBP profile audit via API, cross-platform NAP
   verification, competitor radius map, and review ratings. If not, say what each adds.
7. **Render** a unified local report: strategy actions, NAP matrix, SoLV/geo-grid,
   schema, and (when available) the Tier-1 intelligence visuals.

## Capability routing

This skill follows the plugin's capability-tier cascade
(`references/CAPABILITY-TIERS.md`) and always returns a complete local plan:

1. **Tier 1 — DataForSEO / Google Places MCP.** When connected, pull live per-point
   SERP rank acquisition for the geo-grid, GBP profile data, review ratings, and
   cross-platform citation status.
2. **Tier 2 — built-in (the default).** Otherwise `nap_check.py` builds the
   normalized NAP-consistency matrix and `geogrid.py` computes Share of Local Voice +
   coverage/top-3/avg-rank over supplied rank data (free OSM Nominatim for the grid
   center). This is the product — a real NAP audit + SoLV math with zero spend.
3. **Tier 4 — guided.** If no maps data is available, deliver the NAP matrix, the GBP
   checklist, and a built grid to fill in by hand, and name a maps MCP as the way to
   add live geo-grid rank tracking.

```capability-routing
capability:   local-maps
tier1:        DataForSEO / Google Places MCP
tier1_signal: DATAFORSEO_USERNAME | GOOGLE_API_KEY
tier2:        nap_check.py (NAP consistency matrix) + geogrid.py (SoLV geo-grid math, free OSM Nominatim)
tier2_yields: normalized NAP-consistency matrix + Share-of-Local-Voice over a supplied grid, zero spend
tier3:        none
tier3_signal: none
tier4:        manual NAP + GBP checklist and a built grid to fill in; add a maps MCP for live geo-grid rank tracking
needs_tier1:  live per-point SERP rank, GBP review ratings, citation index count
```

Always end by stating which tier ran and what live maps data a higher tier would add.

## Outputs

| Output | What it contains | Format | Quality bar (how it is scored) |
|---|---|---|---|
| Unified local report | strategy actions (GBP, citations, reviews) + NAP matrix + SoLV + schema | md | every action is specific + prioritized; no "improve your SEO" filler |
| NAP consistency matrix | per-listing name/address/phone match vs canonical, normalized | JSON (`nap_check.py`) + md table | formatting-only diffs normalize away; every real divergence carries a HIGH/MEDIUM severity + the exact fix target |
| SoLV / geo-grid | Share of Local Voice + coverage/top-3/avg-rank over the grid | JSON (`geogrid.py`) + visual | math reproduces on the golden grid; a never-found grid scores 0 (no fabricated rank) |
| LocalBusiness schema | `name`+`address` (req) + `telephone`/`geo`/hours; per-location for multi | JSON-LD (via `seo-schema`) | validates; one block per location with a clean URL |
| Tier line | which tier ran + what live maps data Tier 1 would add | one sentence | states the tier honestly; review ratings / live ranks shipped as `needs_tier1`, never invented |

Filed to: the user's project workspace. Never-fabricate fields (live per-point SERP
rank, GBP review ratings, citation-index counts) ship as a labeled proxy + a
`needs_tier1` list — never a synthesized number.

## Error Handling

| Condition | Detection | Behavior (degrade, never fail) | User-facing message |
|---|---|---|---|
| Maps MCP absent | try DataForSEO/Places; not exposed or errors | run Tier 2 — `nap_check.py` + `geogrid.py` on supplied data | "Ran Tier 2 (built-in NAP + SoLV math). Add a maps MCP for live per-point rank tracking." |
| No network / offline | geocode fetch raises or `--no-network` set | use `--center "lat,lng"` / `--grid FILE`; everything but geocode is offline | "Offline — built the grid from coordinates and ran SoLV; a geocode would resolve an address to a center." |
| Bad / empty input | `nap_check.py` / `geogrid.py` validate and exit non-zero with a JSON error | report the validation error; invent nothing | "Each listing needs a name/address/phone; the grid needs points with lat/lng — here is the expected shape." |
| No rank data yet | grid has only coordinates, no per-point ranks | `--build-grid` returns an un-ranked grid to fill in | "Built an N×N grid; fill each point's rank (a maps MCP or manual checks), then re-run `--grid` for SoLV." |
| URL verification fails | `--verify-urls` fetch blocked (SSRF) or errors | report per-listing `checked:false` + reason; NAP diff still stands | "Couldn't fetch one citation to corroborate; the normalized NAP comparison is unaffected." |
| Missing API credential | `DATAFORSEO_USERNAME`/`GOOGLE_API_KEY` unset (presence probe) | run the free Tier-2 path | "Set `DATAFORSEO_USERNAME` or `GOOGLE_API_KEY` to unlock live geo-grid tracking; delivered Tier 2 meanwhile." |

## Dependencies

- `seo-schema` (LocalBusiness schema) — required for the schema step
- Optional: DataForSEO (intelligence), Google Places API (max coverage)

## Notes

Strategy and intelligence are inseparable in practice, hence the unified skill. The
free path delivers a complete local strategy; intelligence deepens measurement.
Never buy or gate reviews — it's a Google policy violation.
