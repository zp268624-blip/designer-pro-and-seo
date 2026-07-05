# seo-strategy — the evidence-led prompt library (index)

The prompt library `seo-strategy` loads on demand. It is organized as a **six-stage
evidence loop** derived from the deterministic scripts and skills this plugin already
ships — every prompt names the *evidence to gather* (from a free Tier-2 script), the
*decision it drives*, and the *next-stage handoff*, so a plan is never a vanity
deliverable and never a fabricated number.

Knowledge, not steps: the operating procedure lives in `skills/seo-strategy/SKILL.md`.
This library is the reusable prompt set that skill points its Steps at.

## Why these six stages

Each stage is one distinct **evidence subsystem the plugin owns** — not an abstract
framework. The loop is measurement-first: it opens by measuring the starting line and
closes by measuring the delta, and the same drift engine that captures the opening
snapshot captures the closing one, so the plan *compounds* across cycles instead of
resetting each time.

| # | Stage | The decision it produces | Grounding engine subsystem (free Tier-2) |
|---|---|---|---|
| 1 | **Baseline** | the measured starting line + which vertical template governs the plan | `site_map.py` · `crawl_inventory.py` · `business_type.py` · `drift_baseline.py` |
| 2 | **Diagnose** | severity-ranked defects + one honest health score | `tech_audit.py` · `geo_check.py` · `audit_aggregate.py` |
| 3 | **Cluster** | the real content architecture (pillars + spokes + intent) to invest in | `serp_cluster.py` |
| 4 | **Prioritize** | a ranked, dated roadmap by impact x effort x intent | audit severity + cluster centrality + `business_type.py` (scored) |
| 5 | **Produce** | build-ready work orders (briefs + schema + sitemap) | `seo-content-brief` · `schema_gen.py` · `sitemap_tools.py` |
| 6 | **Verify** | proof the metric moved + the next cycle's starting line | `drift_compare.py` · `drift_history.py` · `geogrid.py` |

The order is not decorative: **Diagnose** blocks **Produce** (fix a broken canonical
before you brief a new page onto it), and **Verify** re-enters **Baseline** (its
re-snapshot *is* the next loop's opening measurement). Stages 1 and 6 share the drift
engine on purpose — that shared tool is what closes the loop.

## The stages (folders)

- [`baseline/`](baseline/) — measure the starting state; classify the business so the
  right vertical template governs everything downstream.
- [`diagnose/`](diagnose/) — run the deterministic audits; rank defects by severity;
  roll them into a single re-normalized health score.
- [`cluster/`](cluster/) — map the winnable topic territory by *real SERP overlap* into
  hub-and-spoke architecture with an intent label per node.
- [`prioritize/`](prioritize/) — score every candidate by impact x effort x intent and
  sequence a dated roadmap, ordering blockers ahead of the work they gate.
- [`produce/`](produce/) — convert each prioritized node into a build-ready brief plus
  its structured-data and indexation deliverables.
- [`verify/`](verify/) — re-snapshot and diff to prove the change moved the metric,
  monitor the trend, and hand the delta back to Baseline to start the next cycle.

## The industry-vertical templates (folder)

- [`verticals/`](verticals/) — a strategic **tilt** applied over the same six stages,
  one template per archetype in this plugin's own audience. The archetypes are derived
  from `scripts/seo/business_type.py` (the classifier's own `business_type` + `vertical`
  output), regrouped by strategic posture rather than one-per-type:

  | Template | Covers `business_type.py` output | Strategic center of gravity |
  |---|---|---|
  | [`saas-subscription`](verticals/saas-subscription.md) | `saas` | comparison / integration / use-case pages; trial-driven conversion |
  | [`ecommerce-retail`](verticals/ecommerce-retail.md) | `ecommerce` | product + category architecture; Product/Offer schema; marketplace reach |
  | [`local-service-area`](verticals/local-service-area.md) | `local` + `sab` | GBP, NAP consistency, location pages, SoLV geo-grid, reviews |
  | [`publisher-content`](verticals/publisher-content.md) | `publisher` | topical clusters at volume; freshness; author E-E-A-T |
  | [`professional-b2b-services`](verticals/professional-b2b-services.md) | `agency` + regulated verticals (`legal` / `healthcare` / `finance`) | trust / expertise-led; consultation conversion; citability |

  The count (five) is what the plugin's own audience yields once `local`+`sab` and
  `agency`+regulated verticals are collapsed by shared toolchain and shared posture —
  it is not a fixed target. Add or split a template as a real audience segment earns it.

## How a plan runs

1. Pick the governing **vertical template** from the Baseline classification.
2. Walk stages 1 -> 6, running each stage's prompts against the evidence its scripts
   produce; carry the named artifact to the next stage's handoff.
3. Every roadmap task leaves **Prioritize** already carrying its measurement, so
   **Verify** can prove it — one metric per task, never a vanity deliverable.
4. **Verify** re-enters **Baseline**: the plan is a loop, not a one-shot document.

## Honesty rules the whole library obeys

- **Never fabricate.** Search volume, CPC, keyword difficulty, field Core Web Vitals,
  backlink counts, ranking positions, and organic traffic are emitted as a labeled
  proxy plus a `needs_tier1` list — never a synthesized number. A connector
  (DataForSEO / Semrush / Google APIs) deepens a stage; it is never required to run it.
- **Deterministic evidence first.** Every stage leads with a stdlib script that
  produces a real deliverable offline; the prompt reasons *over* that evidence.
- **State which tier ran.** Each stage says whether it ran on the free path or a
  connector, and what a higher tier would add.
