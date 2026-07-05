# Golden example — seo-cluster (Tier-2: `serp_cluster.py`)

Proves the **free, key-absent Tier-2** path of `seo-cluster`: deterministic
SERP-overlap clustering over an orchestrator-supplied SERP blob, with **no network
and no API key**. This is the built-in product of the `serp-keywords` capability.

> **What this script does NOT do:** it does not fetch SERPs. Acquiring the top
> ranked URLs per keyword is a Claude / WebSearch (or DataForSEO / Semrush) step.
> `serp_cluster.py` is the offline post-processor that turns that blob into a
> hub-and-spoke content architecture. Reproducible offline.

## Input

- `sample-serps.json` — a JSON object `{keyword: [ranked urls]}` for seven
  keywords: three informational "project management basics" variants that share
  three top results, three commercial "best/reviews/top tools" variants that share
  a different three, and one `zephyr tasks login` query (a made-up brand under the
  reserved `.example` TLD) that shares with nobody — so the
  example has two real clusters and one honest singleton to report.

## Command

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/serp_cluster.py" \
  --serps references/examples/seo-cluster/sample-serps.json --threshold 3 --human
```

(From the repo root during development, drop `${CLAUDE_PLUGIN_ROOT}/` and run the
bare `scripts/...` path. Drop `--human` for the default JSON.)

## Expected free deliverable (Tier 2)

Two hub-and-spoke clusters plus a flagged singleton, each with an internal-link
matrix (anchor text per link), e.g.:

```
Cluster 1  [commercial]  (3 keywords)
  PILLAR: best project management software
    - spoke: project management software reviews  [commercial]  (shares 3 URLs with pillar)
    - spoke: top project management tools 2026     [commercial]  (shares 3 URLs with pillar)
  Internal links:
    project management software reviews -> pillar best project management software  anchor="best project management software"
    ...

Cluster 2  [informational]  (3 keywords)
  PILLAR: project management basics
    ...

Singletons (no >=threshold SERP overlap -- need more keywords or data):
    - zephyr tasks login  [navigational]
```

The clustering, the pillar choice, the intent labels, and the link matrix are
complete on their own — that is the product. No keyword volume / CPC / difficulty is
fabricated: those ship in `needs_tier1` and are satisfied only by connecting a
DataForSEO / Semrush MCP (Tier 1). The JSON output (`--serps ... ` without `--human`)
is what `templates/cluster-map.html` renders into an interactive map.
