# Vertical template · Professional & B2B services

**Covers `business_type.py` output:** `agency` (Organization/ProfessionalService schema,
portfolio/case-study language, services/clients language, consultation CTAs) **and** the
regulated verticals the classifier detects — `legal`, `healthcare`, `finance`. Collapsed
into one template because both convert on trust and expertise, not price or cart.
**Center of gravity:** trust and expertise signals (E-E-A-T), consultation-driven
conversion, citability; heightened scrutiny on the regulated (YMYL) verticals.

A strategic **tilt** applied over the six-stage loop.

## What wins here

Buyers are choosing whom to trust with something consequential — a legal case, their
health, their money, or a high-stakes B2B engagement. The winnable territory is
expertise-led: service pages that demonstrate competence, case studies/outcomes, and
authoritative educational content. For the regulated verticals, Trust is the dominant
ranking and conversion signal, and thin or unsourced content is actively penalized.

## Per-stage tilt

- **Baseline** — expect Organization/ProfessionalService schema and portfolio/services
  language; for regulated verticals, flag YMYL early — it raises the E-E-A-T bar for the
  whole plan.
- **Diagnose** — weight **E-E-A-T signals up hardest here**: author credentials, sourcing,
  first-hand markers (`references/shared/eeat-criteria.md`), plus trust pages (about,
  credentials, contact). GEO citability matters — these answers are frequently AI-cited,
  and the citation must trace to an authoritative source.
- **Cluster** — cluster around the service + the questions a prospect asks before buying;
  informational authority content feeds the transactional service pages.
- **Prioritize** — weight **service pages + trust/credential signals up** for near-term
  conversion; authority content compounds behind them. For YMYL, a credibility gap is a
  blocker, not an advisory.
- **Produce** — schema is `Organization`/`ProfessionalService` (+ `LocalBusiness` if the
  firm is location-based); briefs mandate credentials, sourcing, and first-hand experience;
  route trust-page work through `qa-gate`.
- **Verify** — drift watches service-page and trust-page elements; the health score's
  E-E-A-T-heavy categories are the tracked metric; lead/consultation volume is `needs_tier1`.

## Scripts that matter most

`business_type.py` (confirm agency / regulated vertical) -> `geo_check.py` (citability +
authoritative sourcing) -> `serp_cluster.py` (service + pre-purchase question clusters) ->
`schema_gen.py` (Organization/ProfessionalService/LocalBusiness).

## Money vs authority

Money = service pages + case studies + trust pages. Authority = expert educational content
that earns the credibility those pages convert on. For YMYL, treat trust/credibility as a
prerequisite, not a later cycle.
