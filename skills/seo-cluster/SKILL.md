---
name: seo-cluster
description: SERP-overlap semantic topic clustering for content architecture — groups keywords into hub-and-spoke clusters (one pillar + supporting spokes) with an internal-link matrix and intent labels. The free path clusters keywords by actual shared Google results (SERPs acquired via WebSearch, clustered deterministically by serp_cluster.py); DataForSEO/Semrush deepen it with live bulk SERPs and keyword volume/CPC/difficulty. Trigger when the user says "topic cluster", "content cluster", "semantic clustering", "pillar page", "hub and spoke", "content architecture", "keyword grouping", or "cluster plan".
---

# seo-cluster

**Family:** seo
**Status:** Stable

## Purpose

Plan content architecture as **hub-and-spoke clusters**: one pillar page per
cluster, supporting spoke articles linking to and from it, with an internal-link
matrix that specifies anchor text. Keywords are grouped by **SERP overlap** — if
Google returns the same pages for two keywords, they belong on one page; if it
returns different pages, they need separate pages. That shared-result signal, not
word or embedding similarity, is the only one that predicts whether a single URL can
rank for the group (see `references/seo-cluster/serp-overlap-method.md`). The pillar
is the most SERP-central keyword; the spokes specialize under it
(`references/seo-cluster/hub-and-spoke.md`).

## Triggers

- "topic cluster" / "content cluster" / "semantic clustering"
- "pillar page" / "hub and spoke" / "content architecture"
- "keyword grouping" / "cluster plan"

## Inputs

- Seed keywords (or a single seed to expand into a keyword set)
- Cluster-size / overlap threshold; region / language; SERP depth (top-N)

## Steps

1. **Expand seeds** into a keyword set (modifiers, questions, related terms).
2. **Acquire SERPs (this is the acquisition step, not the script).** For each
   keyword, gather the top-ranked URLs into a SERP blob — a JSON object
   `{keyword: [ranked urls]}`. Free path: read SERPs with **WebSearch**. Tier-1
   path: pull bulk live SERPs from a DataForSEO / Semrush MCP when connected.
3. **Cluster deterministically** over that blob:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/serp_cluster.py" \
     --serps serps.json --threshold 3 --top 10 --human
   ```
   `serp_cluster.py` computes pairwise SERP overlap, clusters by shared-URL
   single-linkage at the chosen threshold, classifies each keyword's intent, picks
   the pillar, and emits the internal-link matrix. It **never fetches** anything and
   runs fully offline; it is the deterministic post-processor over the supplied blob.
4. **Review roles** — confirm the pillar (broad/head) and spokes (specific/long-tail)
   per cluster; split any visibly mixed-intent or over-merged cluster (the chaining
   caveat in the method reference).
5. **Render** the cluster map: drop the script's JSON into
   `skills/seo-cluster/templates/cluster-map.html` (replace the
   `/*__SERP_CLUSTER_JSON__*/ null` sentinel — the marker plus the `null` after it — so
   both the template and the injected result stay valid JS) for an interactive
   hub-and-spoke view, plus the link matrix (CSV/markdown). Hand each pillar/spoke to
   `seo-content-brief` to brief the page.

## Capability routing

This skill follows the plugin's capability-tier cascade
(`references/CAPABILITY-TIERS.md`) and always returns a cluster plan:

1. **Tier 1 — DataForSEO / Semrush MCP.** When connected, pull live bulk SERPs per
   keyword (and, separately, keyword volume / CPC / difficulty) to feed clustering at
   scale and to prioritize the resulting pillars.
2. **Tier 2 — built-in (the default).** Otherwise acquire SERPs with **WebSearch**
   and cluster them with `serp_cluster.py` — deterministic SERP-overlap clustering,
   intent labels, pillar selection, and the internal-link matrix, with no key and no
   network in the script. This is the product.
3. **Tier 4 — guided.** If no SERP data can be gathered at all, deliver a manual
   keyword-grouping checklist (group by intent + obvious shared theme) and name
   DataForSEO / Semrush as the way to add live SERPs + volume.

```capability-routing
capability:   serp-keywords
tier1:        DataForSEO / Semrush MCP (live bulk SERPs + keyword volume/CPC/difficulty)
tier1_signal: DATAFORSEO_USERNAME | DATAFORSEO_PASSWORD
tier2:        serp_cluster.py (SERP-overlap clustering over a WebSearch-acquired SERP blob, no key)
tier2_yields: hub-and-spoke clusters + intent labels + internal-link matrix, zero spend
tier3:        none
tier3_signal: none
tier4:        manual keyword-grouping checklist; add DataForSEO/Semrush for live bulk SERPs + volume
needs_tier1:  keyword search volume, CPC, keyword difficulty
```

Always end by stating which tier ran and what volume/SERP-scale data a higher tier
would add.

## Outputs

| Output | What it contains | Format | Quality bar (how it is scored) |
|---|---|---|---|
| Cluster map | Each keyword → its cluster, with pillar vs spoke and an intent label per keyword | JSON (default) + interactive `cluster-map.html` | Every keyword is placed (a clustered member or a flagged singleton); clustering is deterministic — the same blob reproduces it byte-for-byte |
| Hub-and-spoke plan | One pillar + its spokes per cluster, pillar chosen by SERP centrality | JSON `clusters[]` / ASCII `--human` | Exactly one pillar per cluster; every **direct** spoke shares ≥ threshold URLs with the pillar; a member pulled in only through a single-linkage chain (< threshold with the pillar) is flagged `bridged` and never gets a below-threshold pillar link; mixed-intent clusters surfaced for a split |
| Internal-link matrix | Directed links (spoke→pillar, pillar→spoke, spoke→2–3 siblings, and a bridged spoke→its bridge) with anchor text per link | JSON `link_matrix[]` (CSV/markdown on request) | Every direct spoke links up to its pillar with the pillar keyword as anchor; a bridged spoke links up to the member it actually co-ranks with (≥ threshold), never the pillar; sibling links chosen by overlap, capped at 3 |
| Tier line + needs_tier1 | Which tier ran + the never-fabricate fields a higher tier would add | one sentence + list | States the tier honestly; volume/CPC/difficulty ship as `needs_tier1`, never a synthesized number |

Filed to: the user's project workspace (never the plugin). Keyword volume, CPC, and
difficulty are never-fabricate fields — emitted as a labeled `needs_tier1` list until
a DataForSEO / Semrush MCP is connected.

## Error Handling

| Condition | Detection | Behavior (degrade, never fail) | User-facing message |
|---|---|---|---|
| DataForSEO / Semrush MCP absent | the MCP tool is not exposed or errors | acquire SERPs with WebSearch and cluster with `serp_cluster.py` | "Ran Tier 2 (WebSearch SERPs + serp_cluster.py). Add DataForSEO/Semrush for bulk live SERPs + volume." |
| No SERP data obtainable | WebSearch unavailable / blocked | fall back to the manual intent+theme grouping checklist (Tier 4) | "Couldn't gather SERPs — grouped by intent/theme instead; connect a SERP source for overlap-true clusters." |
| Bad / empty SERP blob | `serp_cluster.py` validates: non-object, value not a list, empty, or unparseable JSON → JSON `{"error"}` + non-zero exit | report the validation error; do not invent clusters | "--serps must be a JSON object {keyword: [ranked urls]} — here is the expected shape." |
| Everything is a singleton | script returns clusters=[] with all keywords in `singletons` | report it honestly; suggest lowering `--threshold` or supplying deeper SERPs | "No keywords shared ≥ N results — lower the threshold or add more keywords/top-N depth." |
| Volume/CPC/difficulty requested but no Tier-1 | only the free tier ran | deliver clusters + `needs_tier1` list | "Clusters are ready; volume/CPC/difficulty need a DataForSEO/Semrush MCP (listed in needs_tier1)." |

Every row degrades to a real deliverable — a cluster plan or an honest grouping —
never an empty failure.

## Dependencies

- `scripts/seo/serp_cluster.py` (required) — Python 3.10+, standard library only;
  deterministic, offline SERP-overlap clustering over a supplied blob
- `references/seo-cluster/serp-overlap-method.md`,
  `references/seo-cluster/hub-and-spoke.md` (method + architecture knowledge)
- `seo-content-brief` (optional — briefs each pillar/spoke page)
- Optional: DataForSEO / Semrush MCP (live bulk SERPs + volume/CPC/difficulty)

## Notes

Be explicit about which tier ran. The free path clusters by **real SERP overlap**
(SERPs acquired via WebSearch) — the accurate method — and is the product;
DataForSEO / Semrush only deepen it with scale and the volume/CPC/difficulty numbers
the free path honestly lists under `needs_tier1`. Embedding-only clustering is
deliberately avoided: it produces topically-broad groups Google does not recognize
as one page (see `references/seo-cluster/serp-overlap-method.md`).

Related: `design-research` dispatches `seo-cluster` during its fan-in (one-directional
graph — `seo-cluster` does not depend back on it).
