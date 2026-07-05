---
name: seo-strategy
description: Plans multi-month SEO by business type — measures a baseline, diagnoses defects, maps the winnable topic territory, prioritizes by impact, effort, and intent, then ties every task to a measurable outcome via a six-stage evidence loop and industry-vertical templates. Grounds the keyword universe with seo-cluster when available; otherwise works from a user-provided baseline. Produces a roadmap, content calendar, prioritized investment list, and measurement plan. Trigger when the user says "seo strategy", "seo plan", "seo roadmap", "content strategy", "keyword strategy", "site architecture planning", "evidence-led seo", or "long-term seo plan".
---

# seo-strategy

**Family:** seo
**Status:** Stable

## Purpose

Strategic planning that runs as a **six-stage evidence loop**, grounded in the
deterministic scripts and skills this plugin already ships — so a plan is evidence,
not opinion, and every task is tied to a measurable outcome instead of a vanity
deliverable. The loop is measurement-first: it opens by measuring the starting line
and closes by measuring the delta, and the same drift engine captures both snapshots,
so the plan **compounds** across cycles instead of resetting.

The six stages and the engine subsystem each is grounded in:

1. **Baseline** — measure the starting state (`site_map.py` inventory,
   `business_type.py` classification, `drift_baseline.py` snapshot).
2. **Diagnose** — severity-rank defects (`tech_audit.py`, `geo_check.py`) and roll them
   into one re-normalized health score (`audit_aggregate.py`).
3. **Cluster** — map the winnable topic territory by real SERP overlap
   (`serp_cluster.py`) into hub-and-spoke architecture with intent labels.
4. **Prioritize** — score every candidate by impact × effort × intent and sequence a
   dated roadmap, ordering blockers ahead of the work they gate.
5. **Produce** — convert each prioritized node into a build-ready brief
   (`seo-content-brief`) plus its schema (`schema_gen.py`) and sitemap deliverables.
6. **Verify** — re-snapshot and diff (`drift_compare.py`, `drift_history.py`) plus local
   SoLV (`geogrid.py`) to prove the metric moved, then hand the delta back to Baseline.

The stage-by-stage prompt set — the evidence to gather, the decision each drives, and
the handoff — lives in `references/seo-strategy/prompts/README.md` (the library index).
**Industry-vertical templates** in that library tilt the loop by business type (SaaS,
e-commerce, local & service-area, publisher, professional/B2B services), derived from
this plugin's own `business_type.py` audience.

## Triggers

- "seo strategy" / "seo plan" / "seo roadmap"
- "content strategy" / "keyword strategy"
- "site architecture planning" / "evidence-led seo" / "long-term SEO plan"

## Inputs

- Domain and business type
- Time horizon (3 / 6 / 12 months)
- Current resources (in-house writer? agency budget?)
- Existing keyword baseline (or run `seo-cluster` first)

## Steps

Load `references/seo-strategy/prompts/README.md` and walk the six stages in order,
running each stage's prompts against the evidence its scripts produce.

1. **Baseline.** Inventory the site and classify the business
   (`references/seo-strategy/prompts/baseline/`). Pick the governing **vertical
   template** from the classification; snapshot the pages the plan will touch so every
   later "did it move?" is answerable. Use `seo-audit` for a health snapshot and
   `seo-cluster` for the keyword universe when available; otherwise work from what the
   user provides.
2. **Diagnose.** Run the technical and GEO audits, then aggregate one honest health
   score (`references/seo-strategy/prompts/diagnose/`). Separate blocking defects (fix
   first) from advisory ones.
3. **Cluster.** Map the keyword universe by SERP overlap into pillars + spokes with an
   intent label per node (`references/seo-strategy/prompts/cluster/`).
4. **Prioritize.** Score opportunities by impact × effort × intent and sequence the
   highest-leverage first (`references/seo-strategy/prompts/prioritize/`); every task
   leaves this stage carrying the metric that will prove it.
5. **Produce.** Turn each top roadmap node into a brief plus its schema/sitemap
   deliverables (`references/seo-strategy/prompts/produce/`).
6. **Verify.** Re-snapshot, diff, and monitor to prove each change moved its metric;
   feed the delta back into Baseline (`references/seo-strategy/prompts/verify/`).
7. **Render** the deliverables: a multi-month roadmap (Gantt-style markdown), a content
   calendar, a prioritized investment list, and a measurement plan tied to each task.

## Outputs

| Output | What it contains | Format | Quality bar (how it is scored) |
|---|---|---|---|
| Multi-month roadmap | Dependency-ordered phases; each item has the change, effort, dependency, and its metric | Gantt-style markdown | Every blocking technical/policy fix is sequenced before the work it gates; no item lacks a metric |
| Content calendar | Cluster nodes (pillars + spokes) scheduled across the horizon with page type + intent | markdown table | Each entry traces to a real `serp_cluster.py` node and its intent; no orphan "topic ideas" |
| Prioritized investment list | Candidates ranked by impact × effort × intent, highest-leverage first, with one-line evidence per rank | markdown table | Each rank cites Baseline/Diagnose/Cluster evidence; no rank rests on a fabricated volume number |
| Measurement plan | One metric per task, drawn from the Baseline snapshot or labeled `needs_tier1` | markdown table | Every task pairs with a checkable metric (element diff / health-score / SoLV) or an honest `needs_tier1` |
| Tier line + needs_tier1 | Which tier ran per stage + the never-fabricate fields a connector would add | one sentence + list | States the tier honestly; volume/CPC/field-CWV/rankings/traffic ship as `needs_tier1`, never synthesized |

Filed to: the user's project workspace (never the plugin). Search volume, CPC, keyword
difficulty, field Core Web Vitals, backlink counts, ranking positions, and organic
traffic are never-fabricate fields — emitted as a labeled proxy + a `needs_tier1` list
until a DataForSEO / Semrush / Google connector is present.

## Error Handling

| Condition | Detection | Behavior (degrade, never fail) | User-facing message |
|---|---|---|---|
| No keyword baseline supplied | inputs lack seeds/keywords | run `seo-cluster` to build the universe, or plan from the user's provided pages | "No keyword baseline — I'll run seo-cluster first (or plan from the pages you name)." |
| `seo-cluster` / SERP data unavailable | WebSearch + connector both absent | plan from the Baseline inventory + Diagnose; group opportunities by intent/theme | "Couldn't map SERP-overlap clusters — sequencing from the audit + an intent grouping instead." |
| Optional connector absent (DataForSEO/Semrush/Google) | the MCP/API is not exposed | run every stage on the free Tier-2 scripts; label the connector-only fields | "Ran the free path; volume/field-CWV/rankings are in needs_tier1 — add a connector to fill them." |
| Business type unclassifiable | `business_type.py` returns `unknown` / low confidence | proceed with the generic loop; ask for the missing signal instead of guessing a template | "Couldn't confidently classify the business — name the type so I load the right vertical template." |
| A task has no measurable metric | a roadmap item leaves Prioritize without a metric | send it back: attach a Baseline before-value or a `needs_tier1` metric before it ships | "That task has no metric yet — I've paired it with its drift/health metric so Verify can prove it." |

Every row degrades to a real deliverable — a sequenced, measurable plan — never an
empty failure.

## Dependencies

- `references/seo-strategy/prompts/README.md` (required) — the evidence-led prompt
  library (six stages + vertical templates) this skill's Steps walk.
- `seo-cluster` (optional — grounds the keyword universe; free path if absent)
- `seo-content-brief` (optional — briefs each prioritized cluster node in Produce)

## Notes

The evidence loop keeps the plan honest — every task is tied to a measurable outcome,
not a vanity deliverable, and the loop closes (Verify re-enters Baseline) so successive
cycles compound. Industry-vertical templates keep it concrete per business type.

Related: Step 1 can pull a baseline from `seo-audit`. That is a prose reference, not a
`Dependencies` edge — `seo-audit` is the orchestrator, so listing it here would create a
back-edge in the graph.
