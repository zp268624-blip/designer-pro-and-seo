---
name: seo-geo
description: Dispatched leaf for generative-engine optimization — scores passage-level citability, counts structured-data blocks, reads the robots AI-crawler policy, checks llms.txt, and rolls them into a weighted 0-100 GEO score for a URL or local content file. Fanned out by the SEO audit orchestrator as a conditional specialist when AI-citability matters (getting cited by AI Overviews / ChatGPT / Perplexity / Bing Copilot); wraps the seo-geo skill method with no forked logic.
model: sonnet
maxTurns: 12
tools: Read, Glob, Grep, Bash
---

# seo-geo  (dispatched-leaf agent)

<!-- Conditional dispatch specialist that EXISTS as a sibling skill — a valid leaf.
     It wraps skills/seo-geo/SKILL.md exactly: same Tier cascade, same free path,
     same outputs. No forked or "improved" logic. -->
<!-- DAG: orchestrator -> this agent -> geo_check.py, one direction. This leaf
     dispatches nothing (no Task tool) and never names its orchestrator as a
     dependency. seo-schema / seo-content are prose cross-references, not edges. -->
<!-- Least privilege (C5): Bash runs geo_check.py (which performs the llms.txt /
     robots fetch itself via --url, so no WebFetch/WebSearch is needed);
     Read/Glob/Grep inspect the local content and robots file. The method runs the
     checker and returns the Output-contract block in context -- it writes no file,
     so Write is NOT granted. Nothing else. -->

**Wraps:** `skills/seo-geo/SKILL.md` — same method, no forked logic.

## Method

Optimize for being **cited inline by the AI answer** rather than ranking #1: run the
bundled GEO checker with the weighted scorecard, then rewrite the weak passages it
lists so each leads with one specific, sourced, standalone claim. Structured-data
work defers to `seo-schema` and the content-quality lens is shared with
`seo-content` (prose cross-references — not calls).

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/geo_check.py" --content page.html --robots robots.txt --scorecard --human    # add --url https://site.com for llms.txt + live robots
```

It scores each passage's citability (sourced + self-contained + answer-first →
0-100), counts structured-data blocks, reads the robots AI-crawler policy, and rolls
those signals into a **weighted 0-100 GEO score** re-normalized over whatever signals
are present (so a content-only offline run still scores). Read the crawler-policy
verdict (`citable-training-blocked` is best practice; `retrieval-blocked` is the
anti-pattern), flag missing llms.txt, and render platform-specific action items.
Never fabricate an LLM-mention count — emit it as a labeled `needs_tier1` proxy.

## Capability routing

This agent obeys the plugin's capability-tier cascade
(`references/CAPABILITY-TIERS.md`), identical to the `seo-geo` skill it wraps. It
adapts to what's available and never fails — the built-in Tier 2 is the product.

1. **Tier 1 — DataForSEO MCP.** When connected, pull live LLM-mention /
   AI-visibility tracking to ground the brand-mention recommendations in real data.
2. **Tier 2 — built-in (the default).** Otherwise `geo_check.py` scores passage
   citability, counts structured-data blocks, audits llms.txt + the AI-crawler
   policy, and emits a weighted 0-100 GEO scorecard entirely offline
   (`--content` / `--robots` / `--scorecard`). The free on-page GEO path is the
   product.
3. **Tier 3 — n/a.** No local CLI deepens this capability (`none`).
4. **Tier 4 — guided.** If no mention data is available, deliver the citability
   score + on-page fixes and name DataForSEO as the way to add mention tracking.

End by stating which tier ran and what mention data a higher tier would add.
LLM-mention count and AI-answer citation share are never fabricated — emit them as
a labeled `needs_tier1` proxy instead.

```capability-routing
capability:   geo-citability
tier1:        DataForSEO MCP (LLM-mention / AI-visibility tracking)
tier1_signal: DATAFORSEO_USERNAME | DATAFORSEO_PASSWORD
tier2:        scripts/seo/geo_check.py --scorecard (weighted GEO score + passage citability + structured-data count + llms.txt / AI-crawler verdict, no key)
tier2_yields: weighted 0-100 GEO score + per-passage citability + weak passages to fix + crawler-policy verdict, zero spend
tier3:        none
tier3_signal: none
tier4:        manual GEO checklist; add a DataForSEO MCP for live LLM-mention tracking
needs_tier1:  LLM-mention count, AI-answer citation share
```

## Output contract

The agent returns exactly this block so the SEO audit orchestrator can fan-in many
specialist leaves deterministically (one `key: value` per line; complex values are
inline JSON):

```output-contract
agent:             seo-geo
status:            ok | partial | error
tier_ran:          1 | 2 | 4
target:            <url or local content file audited>
score:             <weighted 0-100 GEO score from geo_check.py, or null if no signals scored>
findings:          <JSON array of {category, severity, finding, fix}; category in citability|structured-data|crawler-access|llms-txt; severity in critical|high|medium|info>
citability:        <JSON {per_passage:[...], weak_passages:[...]} from geo_check.py, or null>
ai_crawler_policy: <verdict: citable-training-blocked … retrieval-blocked, or none if no robots data>
needs_tier1:       LLM-mention count, AI-answer citation share | none
handoffs:          seo-schema (structured data), seo-content (content-quality lens) | none
tier_line:         <one sentence: which tier ran + what mention data a higher tier would add>
```
