---
name: design-research
description: Run a competitive research pass on a target site and its top competitors, producing a structured competitive-intelligence report — brand snapshot, competitor scoring, white-space gaps, and keyword landscape — plus a build brief that feeds the design and SEO workflow. Uses the Firecrawl MCP for deep multi-page scraping when connected; otherwise built-in WebFetch/WebSearch + html-extract. Trigger when the user says "competitive research", "competitor analysis", "research the niche", "niche research", "what are competitors doing", "give me a competitive report", "client research", or "engagement research".
---

# design-research

**Family:** design
**Status:** Stable

## Purpose

The research front-end of an engagement. Given a target domain and a niche, it
captures the target's positioning, identifies top competitors, scores each on key
dimensions, surfaces the white space no one is filling, and produces a markdown or
interactive-HTML report that feeds `design-system-gen`, `design-dimensions`,
`blast-prompt`, and the SEO skills. It is **tool-aware**: with the Firecrawl MCP it
does deep multi-page scraping; without it, built-in web fetch/search + `html-extract`
still produce a real competitive read.

## Triggers

- "competitive research" / "competitor analysis"
- "research the niche" / "niche research"
- "what are competitors doing"
- "give me a competitive report"
- "client research" / "engagement research"

## Inputs

- Target domain
- Industry / vertical
- Geographic scope (local / national / global)
- Number of competitors (default 5)
- Output format: markdown | interactive HTML | both

## Steps

1. **Detect tooling.** Check whether the Firecrawl MCP is connected:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/capability_probe.py"
   ```
   (on Windows use `py` if `python3` is absent; in PowerShell the variable is
   `$env:CLAUDE_PLUGIN_ROOT`). It reports whether `FIRECRAWL_API_KEY` is set.
2. **Capture the target.** Tier 1: Firecrawl-scrape the site for voice, services,
   positioning. Tier 2: WebFetch the key pages + `html-extract` for structure/tokens.
3. **Identify competitors.** Use WebSearch on the niche + the target's core terms to
   assemble a competitor set (default 5); let the user confirm/adjust.
4. **Scan each competitor.** Same tier path as step 2, one pass per competitor.
5. **Score each** on the 18-dimension rubric in
   `data/competitor-rubric.csv` (positioning, brand-craft, content-depth,
   trust-signals, conversion-path, findability). Score every dimension 0–4 against
   its good/bad anchors and roll up the weighted composite exactly as
   `references/design-research/competitor-rubric.md` describes, so scores compare
   across competitors.
6. **Find the white space** — walk each dimension across the whole set and flag the
   ones where *every* competitor is weak (the rubric's `white_space_test` column).
   Read the craft dimensions with the negative-space/rhythm method in
   `references/design-research/white-space-method.md`.
7. **Keyword landscape** — call `seo-cluster` if available; otherwise a WebSearch-based
   intent grouping.
8. **Compose the report** into the user's workspace (see Outputs).
9. **Report which tier ran** and what a full Firecrawl crawl would add.

## Capability routing

This skill follows the plugin's capability-tier cascade
(`references/CAPABILITY-TIERS.md`):

1. **Tier 1 — Firecrawl MCP.** If connected, deep multi-page scraping of target +
   competitors.
2. **Tier 2 — built-in (default).** WebFetch + WebSearch + `html-extract` for a real
   competitive read from the key pages.
3. **Tier 4 — guided.** If a site is JS-rendered and Firecrawl isn't connected, work
   from the pages you can fetch and note what a full crawl would add.

Always state which tier ran and what Firecrawl would add.

## Outputs

Written into the user's project workspace:

| Output | What it contains | Format | Quality bar (how it is scored) |
|---|---|---|---|
| `research/01-target-brand.md` | brand/positioning extraction for the target | md | every claim traces to a fetched page; no invented positioning |
| `research/02-competitor-analysis.md` | each competitor scored 0–4 on all 18 rubric dimensions + six weighted category scores + overall + keyword landscape | md (Critical/High/Medium open-lane groups) | every score cites the `signal_to_check` it was read from; anchors from `data/competitor-rubric.csv`; unobservable dimensions marked "not assessed", never zeroed |
| `research/03-build-brief.md` | the highest-weight open lanes turned into headline build moves | md | each move names the dimension + `white_space_test` it fills; ranked by rubric weight |
| `competitive-analysis.html` (optional) | interactive scoring report (radar/bar over the six categories) | HTML | scale reads 0–4 honestly; no rescale-to-100 implying false precision |
| Tier line | which tier ran + what a full Firecrawl crawl would add | one sentence | states the tier honestly; no fabricated SEO/performance number |

Filed to: the user's project workspace, never into the plugin. A never-fabricate
field (competitor SEO volume, field CWV, backlink counts) ships as a labeled proxy
+ a `needs_tier1` note — never a synthesized number.

## Error Handling

| Condition | Detection | Behavior (degrade, never fail) | User-facing message |
|---|---|---|---|
| Firecrawl MCP absent | `capability_probe.py` reports `FIRECRAWL_API_KEY` unset / MCP not exposed | fall through to Tier-2 WebFetch + WebSearch + `html-extract` | "Ran Tier 2 (built-in fetch). Add Firecrawl for deep multi-page + JS-rendered crawl." |
| A competitor site is JS-gated / auth-walled | key pages fetch empty or a shell | score only the dimensions whose `signal_to_check` was observable; mark the rest "not assessed" | "Couldn't reach <pages> — scored the visible signals; a Tier-1 crawl would complete the rubric." |
| No network / offline | fetch raises or `--no-network` set | analyze provided saved pages / files only | "Offline — scored the provided pages; live fetch would add competitors and freshness signals." |
| Too few competitors found | WebSearch returns < requested set | score what was found; state the smaller n | "Found only <n> credible competitors — scored those; broaden the niche terms to add more." |
| `seo-cluster` unavailable | skill not installed / not routed | fall back to a WebSearch-based intent grouping for the keyword landscape | "Used a WebSearch keyword read; install seo-cluster for SERP-overlap clustering." |
| Bad / empty input (no target domain) | required input missing | ask for the target + niche; do not invent a subject | "A target domain and niche are required to run a competitive pass." |

Every row degrades to a real deliverable; the built-in Tier-2 path is the product.

## Dependencies

- Optional (Tier 1): Firecrawl MCP (`extensions/firecrawl/`) — deep scraping; free
  path works without it
- Built-in (Tier 2): WebFetch; WebSearch; `html-extract`
- `seo-cluster` (optional — adds SERP-based keyword landscape; free path: WebSearch intent grouping)
- `scripts/workflow/capability_probe.py` (required — tooling detection)
- Scoring rubric + method (required knowledge): `data/competitor-rubric.csv`,
  `references/design-research/competitor-rubric.md`,
  `references/design-research/white-space-method.md`

## Notes

The output structure is a proven engagement shape, made repeatable here instead of
bespoke per project. Respect target sites' robots.txt and Terms of Service when
scraping (see `PRIVACY.md`); research artifacts stay in the user's workspace.
