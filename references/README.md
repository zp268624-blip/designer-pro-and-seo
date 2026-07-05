# references/

Deep documentation that skills load on-demand. Lives here (not inline in SKILL.md) to keep skill bodies short and discoverable.

## What goes here

- Protocol-level docs that several skills share (e.g., `parallel-build-protocol.md`)
- WCAG checklists, axe rule references, Schema.org type references
- Industry-vertical guides (restaurant SEO checklist, healthcare LocalBusiness specifics)
- Platform-specific quirks (WordPress block escaping, GoHighLevel embed limits, Webflow CMS bindings)
- Source attribution notes (which external concepts informed which skill, link to the original where appropriate)

## What doesn't go here

- Per-skill operational docs — those belong in the skill's SKILL.md or in `templates/`
- Generated reports — those belong in project workspaces, not the plugin

## Status

In use. Present: `ENGINE-CONTRACTS.md` (interface spec), `CAPABILITY-TIERS.md`
(tool-aware routing cascade, loaded on-demand by several skills), `PROVENANCE.md`
(clean-room ledger), `DEEP-DIVE-ANALYSIS.md` (archived roadmap, kept for
provenance), `README.md` (this file), and `examples/` (golden outputs for shipping
skills). Grows as more skills ship.

## Subfolder convention

*Planned namespaces — created as skills need them; not all are present yet.*

- `references/wcag/` — WCAG 2.2 quick references, axe rule details
- `references/schema/` — Schema.org type cheatsheets
- `references/platforms/` — WP / GHL / Webflow / Wix / Framer / Squarespace specifics
- `references/verticals/` — industry-specific SEO guides
- `references/protocols/` — multi-skill workflows (parallel-build, qa-gate)
