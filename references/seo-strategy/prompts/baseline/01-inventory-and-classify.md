# Baseline · Inventory the site and classify the business

**Loop stage:** Baseline — establish the measured starting line before any judgement.
**When to run:** first, on every new engagement and at the top of each new cycle.

You cannot plan against a site you have not measured. This prompt turns "the site" into
a concrete, classified inventory so the rest of the loop reasons over facts, not a
mental model.

## Evidence to gather (free Tier-2)

- `scripts/seo/site_map.py` — robots.txt + sitemap (urlset/index) discovery plus an
  on-page `<a href>` harvest into a classified URL inventory. In sampled-crawl mode it
  states its sampling boundary ("fetched N of M inventoried URLs") — carry that boundary
  forward; do not treat a sample as the whole site.
- `scripts/seo/crawl_inventory.py` — buckets the discovered URL list into
  page-type / depth / host inventory by URL-path heuristics (offline; does not fetch).
- `scripts/seo/business_type.py` — classifies `business_type` (saas / ecommerce / local /
  sab / publisher / agency) **and** `vertical` from on-page/schema/keyword signals, with
  a confidence and the exact drivers. An empty signal set returns `unknown` / `0.0` — it
  never guesses.

`needs_tier1`: total indexed vs. discoverable counts are a never-fabricate field — report
the sitemap-vs-crawl diff and flag "GSC for authoritative index counts", never a `site:`
number.

## The prompt

> Build the measured baseline for {domain}. Run the site inventory and bucket every URL
> by page type and depth; note the sampling boundary if the crawl was sampled. Feed the
> on-page, schema, and keyword signals to the business-type classifier and record the
> returned `business_type`, `vertical`, confidence, and drivers verbatim — if confidence
> is low or the result is `unknown`, say so and name the missing signal rather than
> asserting a type. Summarize the inventory as a page-type table (count per type, depth
> distribution, orphan/deep pages). Do not estimate index coverage; report the
> sitemap-vs-discoverable diff and list authoritative index counts under `needs_tier1`.

## Decision it drives

- **Which vertical template governs the plan** (from `business_type` + `vertical`).
- **The real page-type mix** the plan must work with (e.g. 240 product pages vs. 6
  location pages) — the shape every later stage plans against.

## Hand off to

- `verticals/` — load the template matching the classification; it tilts every later
  stage.
- `baseline/02-capture-current-state.md` — snapshot the URLs this inventory found.
- `diagnose/` — the audits run against this inventory, not a guessed page list.
