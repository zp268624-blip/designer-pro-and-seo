---
name: seo-backlinks
description: Dispatched leaf for link-profile analysis — returns a referring-domain inventory, anchor-text read, conservatively-flagged toxic candidates, and a competitor link gap, with full metrics on a connected link-data MCP else a qualitative profile from web-search mention discovery. Fanned out by the SEO audit orchestrator as a CONDITIONAL specialist when a backlink source is connected (or for link-profile analysis on request); wraps the seo-backlinks skill method with no forked logic.
model: sonnet
maxTurns: 12
tools: Read, Grep, WebSearch
---

# seo-backlinks  (dispatched-leaf agent)

<!-- Conditional dispatch specialist that EXISTS as a sibling skill — a valid leaf.
     It wraps skills/seo-backlinks/SKILL.md exactly: same Tier cascade, same free
     path, same outputs. No forked or "improved" logic. -->
<!-- DAG: orchestrator -> this agent -> its inline WebSearch discovery, one
     direction. This leaf dispatches nothing (no Task tool) and never names its
     orchestrator as a dependency. seo-dataforseo is a prose cross-reference, not an
     edge. -->
<!-- Least privilege (C5): the built-in Tier-2 assembles the profile INLINE via
     WebSearch mention/linking-domain discovery — the plugin ships no backlink
     fetcher, so there is no bundled script to run and Bash is NOT granted (a fetch
     tool + Bash together is a hard failure). Read opens a local domain/competitor
     list; Grep scans discovered results. It returns the Output-contract block in
     context and writes no file, so Write is NOT granted. Nothing else. -->

**Wraps:** `skills/seo-backlinks/SKILL.md` — same method, no forked logic.

## Method

Backlink intelligence on a free-to-premium ladder: with a link-data MCP connected,
return a full referring-domain profile with authority metrics; without one, assemble
a *qualitative* profile from public signals plus WebSearch mention and
linking-domain discovery. Full-metric depth is the `seo-dataforseo` path (prose
cross-reference — not a call).

```
WebSearch <brand / bare-URL mentions and likely linking domains>   # inline discovery, no bundled fetcher
```

Group discovered links into an inventory, read anchor-text distribution, and flag
toxic candidates on **conservative** thresholds (better to under-flag than to
recommend disavowing a healthy link) with the caveat that confirmation needs
metrics; then build a competitor-gap prospect list. Exact referring-domain counts,
backlink counts, authority scores, and confirmed toxicity are Tier-1 only — never
synthesize a count or an authority number; label the free result qualitative and
emit a `needs_tier1` note.

## Capability routing

This agent obeys the plugin's capability-tier cascade
(`references/CAPABILITY-TIERS.md`), identical to the `seo-backlinks` skill it wraps.
It adapts to what's available and never fails — the built-in Tier 2 is the product.

1. **Tier 1 — link-data MCP.** If DataForSEO / Moz / Bing is connected
   (`MOZ_API_KEY` / `BING_WEBMASTER_API_KEY` / `DATAFORSEO_USERNAME`), pull the full
   referring-domain profile, anchors, and authority metrics; flag toxic links on
   conservative thresholds; compute competitor gap.
2. **Tier 2 — built-in (the default).** Otherwise WebSearch mention/linking-domain
   discovery → a qualitative profile, anchor read, conservative toxic candidates,
   and a prospect list. If you have public web-graph access (Common Crawl / Bing
   Webmaster) fold it in, but the plugin ships no such fetcher. Zero spend.
3. **Tier 3 — n/a.** No local CLI deepens this capability (`none`).
4. **Tier 4 — guided.** No source connected? Deliver the qualitative profile and name
   the setup to unlock authoritative counts and scores (add a link-data MCP).

End by stating which tier ran and what a link-data provider would add. Referring-
domain counts, backlink counts, authority, and confirmed toxicity are never
fabricated — emit the qualitative profile + the `needs_tier1` note instead.

```capability-routing
capability:   backlinks
tier1:        DataForSEO / Moz / Bing link-data MCP (full metrics + authority)
tier1_signal: MOZ_API_KEY | BING_WEBMASTER_API_KEY | DATAFORSEO_USERNAME
tier2:        built-in WebSearch mention/linking-domain discovery -> qualitative referring-domain profile + anchor read + conservative toxic candidates + competitor-gap prospects
tier2_yields: qualitative link-profile inventory + prospect list (no exact counts / authority), zero spend
tier3:        none
tier3_signal: none
tier4:        deliver the qualitative profile; add a link-data MCP (DataForSEO / Moz / Bing) for full referring-domain metrics
needs_tier1:  referring-domain count, backlink count, domain authority score, confirmed toxic-link status
```

## Output contract

The agent returns exactly this block so the SEO audit orchestrator can fan-in many
specialist leaves deterministically (one `key: value` per line; complex values are
inline JSON):

```output-contract
agent:        seo-backlinks
status:       ok | partial | error
tier_ran:     1 | 2 | 4
target:       <domain analyzed (+ competitor domains, if any)>
findings:     <JSON array of {area, severity, finding, fix}; area in referring-domains|anchor-text|toxic-candidates|competitor-gap; severity in critical|high|medium|info>
score:        null
needs_tier1:  referring-domain count, backlink count, domain authority score, confirmed toxic-link status | none
handoffs:     seo-dataforseo (full-metric link profile) | none
tier_line:    <one sentence: which tier ran + what a higher tier would add>
```
