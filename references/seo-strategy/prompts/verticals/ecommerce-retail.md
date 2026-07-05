# Vertical template · E-commerce / retail

**Covers `business_type.py` output:** `ecommerce` (Product/Offer schema, shopping
cart/checkout, add-to-cart and purchase language, many product pages, category pages).
**Center of gravity:** product + category architecture; Product/Offer schema correctness;
marketplace and shopping visibility; index-bloat control.

A strategic **tilt** applied over the six-stage loop.

## What wins here

Revenue lives on category and product pages, and the failure modes are structural:
thin/duplicate product pages, faceted-navigation index bloat, and missing or invalid
Product/Offer schema. The winnable territory is transactional and commercial — category
pages for head terms, product pages for the long tail — with buying-guide content as the
authority layer that feeds them.

## Per-stage tilt

- **Baseline** — the page-type mix is dominated by product/category pages; `crawl_inventory.py`
  depth buckets expose faceted-navigation explosion. Note product count from
  `business_type.py`'s `page_types`.
- **Diagnose** — weight **index-bloat and duplicate-content checks up**: faceted URLs,
  canonical discipline across variants, and thin product descriptions are the classic
  ecommerce drags. Validate Product/Offer schema presence early.
- **Cluster** — cluster by shopping intent; category head terms become pillars, product/
  long-tail become spokes. Buying guides are the informational authority spokes.
- **Prioritize** — weight **transactional intent up**, but sequence index-bloat/canonical
  fixes *before* new category content (they gate crawl budget).
- **Produce** — schema is `Product` + `Offer` (+ `AggregateRating`/`Review` where genuine);
  briefs enforce unique, non-templated product/category copy; hand marketplace/shopping
  work to `seo-ecommerce`.
- **Verify** — drift watches canonical/schema/title on money pages; Shopping/marketplace
  visibility and revenue are `needs_tier1`.

## Scripts that matter most

`business_type.py` (confirm ecommerce + product count) -> `crawl_inventory.py` (bloat
depth buckets) -> `schema_gen.py` (Product/Offer validation) -> `serp_cluster.py`
(category/buying-guide clusters).

## Money vs authority

Money = category and product pages. Authority = buying guides and comparison content.
Fix structure first (bloat/schema), then invest in category depth, then authority.
