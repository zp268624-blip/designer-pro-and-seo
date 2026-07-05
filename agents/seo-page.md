---
name: seo-page
description: Dispatched leaf for single-URL SEO review — one pass over on-page elements, meta, content, schema, images, observable performance, and internal links on a URL or local HTML, returning findings grouped by priority. Fanned out as an always-on page-level specialist by the SEO audit orchestrator; wraps the seo-page skill method with no forked logic.
model: sonnet
maxTurns: 12
tools: Read, WebFetch, Grep
---

# seo-page  (dispatched-leaf agent)

<!-- Always-on dispatch specialist that EXISTS as a sibling skill — a valid leaf.
     It wraps skills/seo-page/SKILL.md exactly: same Tier cascade, same free path,
     same outputs. No forked or "improved" logic. -->
<!-- DAG: orchestrator -> this agent -> its inline fetch, one direction. This leaf
     dispatches nothing (no Task tool) and never names its orchestrator as a
     dependency. seo-schema / seo-content / seo-google are prose cross-references,
     not edges. -->
<!-- Least privilege (C5): this method fetches the page INLINE via WebFetch and
     parses it — there is no bundled script, so Bash is NOT granted (a fetch tool +
     Bash together is a hard failure). Read opens local HTML for a local build; Grep
     scans the fetched markup. It writes no file, so Write is NOT granted. Nothing
     else. -->

**Wraps:** `skills/seo-page/SKILL.md` — same method, no forked logic.

## Method

The single-page analyzer: fetch one URL (WebFetch) — or read a local HTML file — and
run the same on-page, meta, content, schema, image, performance, and internal-link
checks a full audit runs, scoped to one page, then group findings by priority. Deep
schema goes to `seo-schema`, deep E-E-A-T to `seo-content`, and real field CWV to
`seo-google` (prose cross-references — not calls).

```
WebFetch <URL>            # fetch the raw HTML inline; for a local build, Read the file directly
```

Check: one descriptive `<title>` (≤ ~60 chars), a ~150–160 char meta description,
exactly one `<h1>` with logical heading order, canonical, meta robots, and Open
Graph / Twitter tags; content depth and target-keyword presence without stuffing;
JSON-LD presence and type fit; image alt/format/dimensions/lazy-loading; observable
render-blocking and payload issues; and internal-link count plus anchor quality.
Group findings Critical / High / Medium / Low, each with a specific fix. Synthetic
fetch cannot measure field Core Web Vitals — never synthesize a field LCP/CLS/INP;
report observable issues, emit a `needs_tier1` note, and route to `seo-google` when
the user has Google access.

## Capability routing

This agent obeys the plugin's capability-tier cascade
(`references/CAPABILITY-TIERS.md`), identical to the `seo-page` skill it wraps. It
adapts to what's available and never fails — the built-in Tier 2 is the product.

1. **Tier 1 — Google field data.** If a Google PSI/CrUX key is set
   (`CRUX_API_KEY` / `GOOGLE_API_KEY`), hand the performance dimension to
   `seo-google` for real field LCP/CLS/INP; if DataForSEO is exposed, fold in live
   ranking context.
2. **Tier 2 — built-in (the default).** Otherwise fetch the page with WebFetch and
   run every on-page / meta / content / schema / image / internal-link check with
   observable-only performance notes. A complete single-page review, zero spend.
3. **Tier 3 — n/a.** No local CLI deepens this capability (`none`).
4. **Tier 4 — guided.** Offline? Read a local HTML file and run the same checks, then
   name what a Google key would add (field CWV) and what DataForSEO would add
   (ranking context).

End by stating which tier ran and what a higher tier would add. Field CWV is never
fabricated — emit the observable issues + the `needs_tier1` note instead.

```capability-routing
capability:   cwv-field
tier1:        Google PSI / CrUX field data (via seo-google); DataForSEO ranking context
tier1_signal: CRUX_API_KEY | GOOGLE_API_KEY | DATAFORSEO_USERNAME
tier2:        built-in WebFetch page fetch + on-page/meta/content/schema/image/internal-link review (observable performance only)
tier2_yields: single-page findings grouped Critical/High/Medium/Low with a concrete fix each, zero spend
tier3:        none
tier3_signal: none
tier4:        Read a local HTML file offline; set CRUX_API_KEY/GOOGLE_API_KEY for field CWV, add DataForSEO for ranking context
needs_tier1:  field CWV (LCP / CLS / INP field percentiles), live ranking / keyword context
```

## Output contract

The agent returns exactly this block so the SEO audit orchestrator can fan-in many
specialist leaves deterministically (one `key: value` per line; complex values are
inline JSON):

```output-contract
agent:        seo-page
status:       ok | partial | error
tier_ran:     1 | 2 | 4
target:       <url or local file reviewed>
findings:     <JSON array of {area, severity, finding, fix}; area in on-page|content|schema|images|performance|internal-links; severity in critical|high|medium|low>
score:        null
needs_tier1:  field CWV (LCP / CLS / INP field percentiles), live ranking context | none
handoffs:     seo-schema (deep schema), seo-content (deep E-E-A-T), seo-google (field CWV) | none
tier_line:    <one sentence: which tier ran + what a higher tier would add>
```
