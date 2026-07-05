---
name: seo-google
description: Dispatched leaf for Google field data — returns real Search Console analytics (impressions, clicks, CTR, position), URL Inspection and sitemap status, CrUX/PSI field Core Web Vitals, and GA4 organic when connected, else a built-in on-page technical + GEO read that names exactly what to connect. Fanned out by the SEO audit orchestrator as a CONDITIONAL specialist when a Google PSI/CrUX/GSC key or MCP is connected; wraps the seo-google skill method with no forked logic.
model: sonnet
maxTurns: 12
tools: Read, Glob, Grep, Bash
---

# seo-google  (dispatched-leaf agent)

<!-- Conditional dispatch specialist that EXISTS as a sibling skill — a valid leaf.
     It wraps skills/seo-google/SKILL.md exactly: same Tier cascade, same free path,
     same outputs. No forked or "improved" logic. -->
<!-- DAG: orchestrator -> this agent -> tech_audit.py / geo_check.py, one direction.
     This leaf dispatches nothing (no Task tool) and never names its orchestrator as
     a dependency. seo-technical / seo-geo are prose cross-references, not edges. -->
<!-- Least privilege (C5): the built-in Tier-2 path RUNS bundled scripts
     (capability_probe.py, tech_audit.py, geo_check.py), so Bash is granted and the
     built-in fetch tools are NOT (a fetch tool + Bash together is a hard failure --
     the scripts perform their own fetching). Read/Glob/Grep inspect local HTML and
     config. The method returns the Output-contract block in context -- it writes no
     file, so Write is NOT granted. Nothing else. -->

**Wraps:** `skills/seo-google/SKILL.md` — same method, no forked logic.

## Method

The "real field data" layer: when a Google Search Console / Google MCP (or Google
APIs) is connected, return Google's own measurements — GSC search analytics, URL
Inspection and sitemap status, CrUX/PSI field Core Web Vitals, GA4 organic; when
nothing is connected, still deliver a real on-page technical + GEO read and name
precisely what to connect. `seo-technical` covers the synthetic/lab side and
`seo-geo` the AI-citability depth (prose cross-references — not calls).

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/capability_probe.py"     # which Google env keys are set
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/tech_audit.py" --url <URL> --human
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/geo_check.py"   --url <URL>
```

CrUX/PSI field CWV, GSC impressions/clicks/CTR/position, and GA4 organic traffic are
field measurements a synthetic run cannot produce. Core Web Vitals targets: **LCP <
2.5s, CLS < 0.1, INP < 200ms** (INP, not FID). Never synthesize a field number —
when no Google tool is connected, emit the lab targets + on-page/GEO findings, a
`needs_tier1` note, and the one-line setup to unlock field data.

## Capability routing

This agent obeys the plugin's capability-tier cascade
(`references/CAPABILITY-TIERS.md`), identical to the `seo-google` skill it wraps. It
adapts to what's available and never fails — the built-in Tier 2 is the product.

1. **Tier 1 — Google data.** If a Search Console / Google MCP or Google APIs are
   connected (`CRUX_API_KEY` / `GOOGLE_API_KEY`), use them for true field data — GSC
   analytics, CrUX field CWV, GA4 organic.
2. **Tier 2 — built-in (the default).** Otherwise WebFetch's job is done by the
   scripts: run `tech_audit.py` (on-page technical + lab CWV targets) and
   `geo_check.py` (AI-citability + llms.txt) for a real on-page read. Zero spend.
3. **Tier 3 — n/a.** No local CLI deepens this capability (`none`).
4. **Tier 4 — guided.** Offline? Run `tech_audit.py --file page.html` for the on-page
   read and name the field-data gap (connect a Search Console MCP, or set a Google
   PSI/CrUX key).

End by stating which tier ran and what connecting Google would add. Field CWV, GSC
metrics, and GA4 traffic are never fabricated — emit the on-page read + the
`needs_tier1` note instead.

```capability-routing
capability:   cwv-field
tier1:        Google Search Console / PSI / CrUX / GA4 (field data)
tier1_signal: CRUX_API_KEY | GOOGLE_API_KEY
tier2:        scripts/seo/tech_audit.py (on-page technical + LCP<2.5 / CLS<0.1 / INP<200 targets) + scripts/seo/geo_check.py (AI-citability)
tier2_yields: on-page technical + GEO read with lab CWV targets, zero spend
tier3:        none
tier3_signal: none
tier4:        run tech_audit.py --file offline; connect a Search Console MCP or set CRUX_API_KEY/GOOGLE_API_KEY for field data
needs_tier1:  field CWV (LCP / INP / CLS percentiles), GSC impressions / clicks / CTR / position, indexation status, GA4 organic traffic
```

## Output contract

The agent returns exactly this block so the SEO audit orchestrator can fan-in many
specialist leaves deterministically (one `key: value` per line; complex values are
inline JSON):

```output-contract
agent:        seo-google
status:       ok | partial | error
tier_ran:     1 | 2 | 4
target:       <domain or page URL analyzed>
findings:     <JSON array of {signal, severity, finding, fix}; signal in search-analytics|url-inspection|field-cwv|indexation|ga4-organic|on-page|geo; severity in critical|high|medium|info>
score:        null
needs_tier1:  field CWV (LCP / INP / CLS percentiles), GSC impressions / clicks / CTR / position, indexation status, GA4 organic traffic | none
handoffs:     seo-technical (lab technical), seo-geo (AI-citability depth) | none
tier_line:    <one sentence: which tier ran + what a higher tier would add>
```
