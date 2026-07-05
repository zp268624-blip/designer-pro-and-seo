# Golden example — seo-geo (Tier-2: `geo_check.py`)

Proves the **free, key-absent Tier-2** path of `seo-geo` scores passage citability,
the AI-crawler-policy verdict, and the **weighted 0-100 GEO scorecard** with no network
and no API key — the `geo-citability` capability's built-in product. Reproducible offline.

## Input

- `sample-content.html` — a short answer page with one strongly citable passage
  (specific number + date + named source) and one weak, unsourced passage, so the
  scorer has both a pass and a fail to report.
- `sample-robots.txt` — a "citable, opted out of training" policy (retrieval bots
  allowed, training crawlers blocked) so the crawler verdict has real rules to judge.

## Command

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/geo_check.py" \
  --content references/examples/seo-geo/sample-content.html \
  --robots references/examples/seo-geo/sample-robots.txt \
  --scorecard --no-network --human
```

(From the repo root during development, drop `${CLAUDE_PLUGIN_ROOT}/` and run the
bare `scripts/...` path. Drop `--robots`/`--scorecard` for the original
content-only citability read.)

## Expected free deliverable (Tier 2)

A weighted GEO scorecard + citability report + crawler verdict, e.g.:

```
GEO score: 68/100 (developing) [weighted over 90/100 available]
  - passage_citability: 80 (mean passage citability)
  - structured_data: 0 (0 JSON-LD block(s))
  - ai_crawler_access: 100 (retrieval open)
  - llms_txt: n/a (not checked — pass --url)
Passage citability: 1/2 passages citable (50%); mean readiness 80/100
  - "Cedar resists rot because its natural oils repel moisture..." — no
    specific/verifiable signal (add a number, date, or named source)
Structured data blocks: 0
AI crawler policy: citable-training-blocked — Best-practice posture: retrieval bots
    allowed (stays citable) while training crawlers are blocked.
```

The scorecard re-normalizes over the available categories (here 90/100, since
`llms_txt` needs `--url`), so the offline run still yields an honest number. No
LLM-mention count is fabricated. `needs_tier1` (LLM-mention count, AI-answer
citation share) is satisfied only by connecting a DataForSEO MCP (Tier 1). The
scorecard + fix list + verdict above are complete on their own — the product.
