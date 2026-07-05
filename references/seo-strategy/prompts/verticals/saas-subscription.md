# Vertical template · SaaS / subscription software

**Covers `business_type.py` output:** `saas` (SoftwareApplication schema, subscription /
recurring billing, free-trial and sign-up CTAs, API/integrations language, pricing/plans).
**Center of gravity:** comparison, integration, and use-case pages; trial-driven conversion;
topical authority over local signals.

A strategic **tilt** applied over the six-stage loop — it changes the weights, not the
stages.

## What wins here

Buyers evaluate before they sign up: they compare alternatives, check integrations, and
look for their exact use case. The winnable territory is bottom-of-funnel commercial
content (comparisons, alternatives, integration pages) sitting on top of an authority
layer of use-case and category guides. Local signals are near-irrelevant.

## Per-stage tilt

- **Baseline** — expect a `saas` classification with SoftwareApplication schema and
  pricing/trial signals. Inventory the docs/blog/comparison surface separately from the
  marketing site; these have different intents.
- **Diagnose** — technical health of the app-marketing boundary matters (JS-rendered
  marketing pages; canonical between `/pricing` variants). GEO citability is high-value:
  SaaS answers are frequently lifted into AI results, so weight `geo_check.py` up.
- **Cluster** — prioritize commercial clusters ("X vs Y", "alternatives to X", "X for
  {use case}", "X {integration}"). These co-rank tightly and convert.
- **Prioritize** — weight **commercial/transactional intent up**: a comparison page that
  captures active evaluators outranks a broad top-of-funnel guide for near-term ARR.
- **Produce** — briefs lean on differentiation against named competitors; schema is
  `SoftwareApplication` + `Offer`; comparison pages get the plugin's `seo-competitor-pages`
  treatment.
- **Verify** — the drift-tracked metric is element/citability change; ranking/trial-signups
  are `needs_tier1` (GSC/GA4).

## Scripts that matter most

`business_type.py` (confirm saas) -> `geo_check.py` (citability of answer content) ->
`serp_cluster.py` (comparison/integration clusters) -> `schema_gen.py` (SoftwareApplication/Offer).

## Money vs authority

Money = comparison/alternatives/integration pages. Authority = use-case and category
guides that feed them. Bias the first two cycles toward money, then broaden authority.
