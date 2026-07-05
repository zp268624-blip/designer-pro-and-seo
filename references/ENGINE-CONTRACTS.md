# Engine Contracts & Authoring Conventions

The interface spec every skill body, script, and template in this plugin must
follow. Designed **before** filling skill bodies so the interface is stable and we
don't harden a bad one. If a skill violates a contract here, the skill is wrong.

---

## 1. SKILL.md structure (canonical order)

Every `SKILL.md` uses this exact section order:

```
---
name: <kebab-case, matches folder>
description: <one line: what it does + "Trigger when the user says ...">
---

# <name>

**Family:** <build-and-qa | design | seo | content-and-data | business-and-gtm | routing>
**Status:** <Stable | In development — ...>

## Purpose
## Triggers
## Inputs
## Steps
## Capability routing   <-- OPTIONAL: only when the skill declares a tier cascade
## Outputs
## Dependencies      <-- Dependencies ALWAYS before Notes
## Notes
```

Rationale for Dependencies-before-Notes: dependencies are operational (the agent
needs them to run the skill); notes are context. Operational content comes first.
Existing scaffolds may still show Notes-before-Dependencies; fix on next edit.

**`## Capability routing` is an optional section** placed in the canonical order
**between `## Steps` and `## Outputs`** (the tier cascade is operational — it
decides *how* the steps execute — and it feeds the outputs). A skill includes it
only when it declares a Tier-1→Tier-4 cascade (see `CAPABILITY-TIERS.md`); skills
with no optional tooling omit it entirely. The section-order checker therefore
treats `## Capability routing` as **optional**: when present it must sit between
`## Steps` and `## Outputs`; when absent the order is still valid. Adding the
section to a skill that already follows the order never trips the check.

## 2. Naming convention

- **Family-prefixed** names for skills that belong to a coherent family and are
  usually invoked through an orchestrator: `seo-*`, `design-*`, `route-*`.
- **Bare action names** for standalone, cross-family *workflow* skills that aren't
  owned by one family: `qa-gate`, `parallel-build`, `blast-prompt`,
  `portable-html-port`, `html-extract`, `client-outreach`, `csv-to-report`.

This is deliberate, not an inconsistency: the prefix signals family membership;
its absence signals a top-level workflow. Do not rename existing skills (it breaks
cross-references); apply the rule to new skills.

## 3. Trigger-qualification rule (prevents wrong-skill firing)

Generic verbs (`audit`, `review`, `check`, `generate`, `build`, `optimize`,
`analyze`, `report`) MUST be domain-qualified in the `Triggers` list. Never list a
bare generic verb as a trigger.

- ✅ "seo audit", "wcag audit", "technical audit", "backlink audit"
- ❌ "audit", "audit this"
- ✅ "review the code you wrote", "review this design", "conversion review"
- ❌ "review", "review this"

Cross-domain skills (the `route-*` family especially) must scope their triggers to
their actual lane — e.g. routing-review triggers on *Claude's own output*
("review the code you wrote", "check your work"), not on bare "audit this", which
belongs to the SEO/QA families.

## 4. Dependency direction (must form a DAG)

`Dependencies` lists what a skill *calls*. Edges must be one-directional:
**orchestrator → specialist**, never back. A specialist must not list its
orchestrator as a dependency. If two skills genuinely relate but neither owns the
other, reference each other under **Notes ("Related skills")**, not under
Dependencies. (Cross-references in prose are fine; hard Dependency cycles are not.)

Known hubs (many depend on them): `design-system-gen`, `seo-schema`,
`seo-dataforseo`. Keep their own Dependencies minimal.

**Amendment (DAG spans agents too).** The dependency DAG covers **skills *and*
agents**, one direction only: **orchestrator → agent → script**. Agents never call
agents; a specialist never lists its orchestrator. A mutual relationship stays a
Notes-level cross-reference (prose), never a Dependencies edge. **Shared-hub leaves
are legal:** a specialist with many in-edges (e.g. `seo-schema`, or `seo-firecrawl`
as a routing target) is valid — the parity check treats many→one as a hub, not an
orphan or a cycle. See §11 for the agent layer this amendment governs.

## 5. Graceful degradation (the free path is the product)

Most users will not have paid MCPs (DataForSEO, Firecrawl, nanobanana) or Google
API auth. Therefore:

- Every skill that *can* use an optional tool MUST also have a **free/manual
  path** that produces real value without it.
- At runtime the skill must **detect** whether the optional tool is available
  (see §6) and:
  1. If present → use it.
  2. If absent → run the free path AND print one line stating what the paid path
     would add. Never just fail or return nothing.
- The `Dependencies` section must label each dependency `(required)` or
  `(optional — adds X; free path: Y)`.

## 6. Dependency detection pattern

Skills detect optional tooling before using it:

- **CLI tools** (python, node, playwright, codex, gemini): check availability and
  fall back. On Windows the Python launcher is `py`; on macOS/Linux it's
  `python3`. Scripts must be invoked in a way that works on both, or the skill
  must try `python3` then `py`.
- **MCP servers** (Firecrawl/DataForSEO/nanobanana): check whether the MCP tool is
  exposed in the session; if not, state the install path (see `extensions/`).
- **API credentials**: read from environment variables only; if missing, run the
  free path and tell the user which env var to set.

## 7. Scripts contract (`scripts/`)

- Python 3.10+, **standard library preferred**; declare any dep in a per-folder
  `requirements.txt`.
- Each script is runnable standalone (CLI) **and** importable as a library.
- **stdout = machine-readable JSON by default**; add a `--human` flag for ASCII.
- **Idempotent**: same inputs → same outputs.
- Tolerate partial data (e.g. the design engine works with whatever CSVs exist
  and notes which dimension fell back to heuristics).
- Exit non-zero on real failure with a clear stderr message.

## 8. Secrets handling (hard rule)

- Never hard-code credentials. Read from environment variables.
- **Never** print or log API keys, tokens, or secrets to stdout, files, or
  reports — including in error messages and debug output.
- Never write scraped client data outside the user's project workspace.
- Respect target sites' robots.txt and Terms of Service when crawling.

## 9. Acceptance criteria (a skill is "done" only when…)

See `SHIPPING.md` → "Promotion checklist". In short: real Steps, all referenced
assets exist, graceful degradation works, description matches behavior, a golden
example exists under `references/examples/`, and Status reads `Stable`.

## 10. Output filing convention

Skills write generated artifacts into the **user's project workspace**, not into
the plugin. The plugin ships read-only content (skills, scripts, data, templates,
references). Generated reports, design systems, screenshots, and HTML go to the
project the user is working on.

---

## 11. Agents (`agents/`)

The agent layer (`agents/*.md`) holds real Agent-tool subagents the orchestrators
dispatch in parallel. It is additive and auto-discovered — no manifest churn.

- **An agent exists only for a dispatched *leaf*.** Author an agent for a
  specialist an orchestrator actually fans out to; **never** author an agent for an
  orchestrator (orchestrators dispatch, they are not dispatched). The roster is
  *derived* from what is wired this release, authored **just-in-time** in the wave
  that wires it — the count is whatever falls out, never a target.
- **No forked method.** An agent **wraps the same method as its sibling skill** —
  same Tier cascade, same free path, same outputs. It must not re-implement,
  diverge from, or "improve on" the skill's logic. One behavior, two entry points
  (skill = inline; agent = dispatched).
- **Required frontmatter:** `name`, `description`, `model`, `maxTurns`, and a
  **least-privilege `tools`** list. Grant only the tools the agent needs: a
  fetch-only agent gets no `Bash`; an agent that fetches untrusted URLs may not also
  hold write/exec privilege it does not use. Over-privilege fails the gate (C5).
- **Two required body blocks:**
  1. **`## Capability routing`** — the Tier-1→Tier-4 cascade the agent obeys (same
     contract as the optional skill section; see `CAPABILITY-TIERS.md`).
  2. **`## Output contract`** — a **machine-parseable** block (fixed keys / fenced
     schema) so the orchestrator can fan-in results deterministically. State which
     tier ran and surface any `needs_tier1` list; never emit a fabricated number.
- **DAG membership.** Agents are nodes in the §4 DAG: orchestrator → agent →
  script, one direction; agents never call agents; shared-hub leaves are legal.
- **Parity (C3).** Every leaf an orchestrator names must have exactly one agent on
  disk and vice-versa (many→one hubs excepted); do not mirror any third-party
  always/conditional dispatch *shape*.

## 12. Per-skill references (`skills/<name>/references/`)

Depth files a SKILL.md loads **on demand** so the body stays lean.

- **Earned, not default.** A skill gets a reference only when it has real depth to
  hold; most skills stay single-file until they earn one. Reference *count is
  incidental* — never matched to any external per-skill count.
- **Named-path loads.** The SKILL.md cites each reference by exact path (e.g.
  `references/scoring-weights.md`); every cited path must resolve on disk (C1).
- **Knowledge, not steps.** A reference holds *durable knowledge* — rubrics,
  thresholds, method, worked examples — not procedure. Steps live in `## Steps`.
- **Lean.** Keep each under **~200 lines**; split rather than sprawl.
- **Clean-room, source-closed for high-risk classes.** For any reference that
  mirrors an inspiration topic (drift rules, ranking method, prompt-adjacent
  rubrics), author **from a capability bullet list with the source text NOT open**,
  and record the method note in `PROVENANCE.md` (basis = our own engine/elements).

## 13. Templates & prompt libraries (`templates/`, `references/prompts/`)

- **Original wording only**, authored from first principles or public standards;
  high-risk libraries (e.g. the evidence-led SEO prompts) authored **source-closed**.
- **No third-party attribution headers** in shipped/user-facing files — no
  `<!-- Source: … -->`, no `CC BY` / `Creative Commons` / `Synced:` / `© <name>`
  banners. Legitimate attribution (if ever required) lives only in `NOTICE.md`.
- **No sync scripts** (`sync_*` prompt fetchers) and **no `*-prompts.lock`**
  (positive or external). Git history is the integrity record; C9 forbids both.

## 14. Hooks — SPEC ONLY (layer deferred)

The `hooks/` layer is deferred to a post-v1 follow-up; this spec exists so it is
born-compliant when built. No hook ships in v1.

- **stdlib-only** Python, same zero-dependency posture as `scripts/`.
- **Exit-code contract:** `0` = pass, `1` = warn, `2` = block. A hook is a thin
  wrapper around the **existing validators** (`schema_gen.py`, `verify_release.py`,
  the clean-room guard) — it never re-implements their checks.
- **Fail-open on its own bugs:** on anything **unparseable** or unexpected, exit
  `0` (never block a deliverable on a hook defect).
- **Never print secret values** — not in pass/warn/block output, not in errors.

## 15. Connectors & SSRF safety

- **stdlib-first.** A connector is a Tier-1 accelerator over a complete stdlib
  Tier-2; the free path never depends on a connector being present.
- **One shared `validate_url()` is mandatory** for *any* script that fetches a URL:
  import the single `scripts/workflow/net_safety.py` guard (blocks private /
  loopback / reserved / cloud-metadata IPs and `user@host` userinfo bypass). SSRF
  protection is a **contract**, not a per-script nicety — no inline ad-hoc allowlist.
- **Secrets are env-only and never printed** (extends §8) — keys read from
  environment variables, never logged to stdout, files, or reports.
- **Cost-guard fail-open.** `cost_guard.py` gates paid calls, but any cost-guard
  error or unavailability **falls through to the free Tier-2** — a connector-safety
  bug can never block the free path or a deliverable.

## 16. Free-path is mandatory (the product invariant)

- **Every connector skill *and* agent ships a real Tier-2** — a stdlib/built-in
  path that produces a genuine deliverable with no paid tool, no key, no MCP.
- **An empty Tier-2 cannot be `Stable`.** CI (C4) refuses `Stable` to any connector
  skill whose Tier-2 is empty or whose named Tier-2 script is missing on disk; the
  Tier-2 must be exercised by a golden example.
- **Never fabricate when only the free tier is available.** SERP volume, field CWV,
  backlink counts, review ratings, GA4 traffic, and indexed/excluded page counts
  ship as a **labeled proxy + a `needs_tier1` list**, never a synthesized number.
- **One exemption:** `seo-image-gen` is **exempt-by-spec** (image-pixel generation
  has no free substitute). It ships an **image-spec substitute** as its documented
  Tier-2 (exact dimensions, alt text, OG meta, schema `image`) and its description
  must not imply a free pixel path.

---

## Note — skill-behavior testing

Beyond file/contract validity, skills and agents are pinned by **behavior tests**
(`tests/test_skill_behavior.py`; lands with the W2 scaffold, grows per enriched
skill). They assert a skill **triggers** on its quoted phrases and **not** on a
sibling's, **dispatches** to the right specialist/agent, **falls back** to its
Tier-2 when a connector/MCP is absent (the free path actually runs), and makes
**honest completion claims** (states which tier ran; emits no fabricated number).
This is a first-class discipline — contract conformance is necessary but not
sufficient.
