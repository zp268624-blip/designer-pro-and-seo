# Skill section template — the uniform shape later skills fill

Knowledge, not steps. This is the fill-in shape every enriched `SKILL.md` adopts so
the suite reads uniformly and the gate can check it mechanically. It pins three
things: where the **optional `## Capability routing`** block sits in the canonical
order, a scored **`## Outputs`** table, and an **`## Error Handling`** table. It does
not replace `ENGINE-CONTRACTS.md` section 1 (the authoritative section order) — it
fills in the two tables that order leaves unspecified.

---

## Where it sits (canonical order, ENGINE-CONTRACTS section 1)

```
## Purpose
## Triggers
## Inputs
## Steps
## Capability routing   <-- OPTIONAL: present ONLY when the skill declares a Tier-1..Tier-4 cascade.
                            When present it MUST sit here, between Steps and Outputs.
                            When absent the order is still valid (skills with no optional
                            tooling omit it entirely). See CAPABILITY-TIERS.md for the
                            prose + the fenced `capability-routing` block grammar.
## Outputs
## Error Handling       <-- sits with Outputs (what the skill emits, and what it does when it can't).
## Dependencies         <-- Dependencies ALWAYS before Notes.
## Notes
```

The `## Capability routing` body is the prose paragraph **plus** one fenced
`capability-routing` block per capability (machine-parseable; `tier2` required and
must name a script that resolves on disk and is exercised by a golden example).

---

## `## Outputs` — scored table template

Each output names what it is, its format, and the **quality bar it is graded
against** (so "done" is checkable, not vibes). Artifacts are written into the
**user's project workspace**, never into the plugin (ENGINE-CONTRACTS section 10).

```markdown
## Outputs

| Output | What it contains | Format | Quality bar (how it is scored) |
|---|---|---|---|
| <primary artifact> | <the real deliverable> | <md / JSON / HTML / CSS> | <the rubric or threshold it must clear> |
| <secondary finding> | <prioritized findings + fixes> | <Critical/High/Medium/Info groups> | <every finding carries a specific fix> |
| <tier line> | which tier ran + what a higher tier would add | one sentence | states the tier honestly; no fabricated number |

Filed to: the user's project workspace. A never-fabricate field (SERP volume, field
CWV, backlink counts, review ratings, GA4 traffic, indexed/excluded page counts)
ships as a labeled proxy + a `needs_tier1` list — never a synthesized number.
```

Guidance: keep the table to the outputs the skill actually emits; the **quality
bar** column is the load-bearing part — it is what a reviewer (and a future golden
example) checks the run against.

---

## `## Error Handling` — graceful-degradation table template

The free path is the product, so the table's job is to show the skill **never just
fails**: every failure mode detects, degrades, and tells the user the next step.

```markdown
## Error Handling

| Condition | Detection | Behavior (degrade, never fail) | User-facing message |
|---|---|---|---|
| Optional Tier-1 tool absent | try the MCP/API; it is not exposed or errors | fall through to the built-in Tier-2 path | "Ran Tier 2 (built-in <script>). Add <tool> for <what it adds>." |
| No network / offline | fetch raises or `--no-network` set | run the offline/`--file` path | "Offline — analyzed the provided file; live fetch would add <X>." |
| Bad / empty input | script validates and exits non-zero with JSON error | report the validation error; do not invent data | "<field> is required / unparseable — here is the expected shape." |
| Paid call would exceed budget | cost-guard estimate over cap | cost-guard fails open to free Tier-2 | "Skipped the paid call (budget); delivered the free-path result." |
| Missing API credential | env var unset (presence-only probe) | run the free path | "Set <ENV_VAR> to unlock <higher tier>; delivered Tier 2 meanwhile." |

Every row degrades to a real deliverable. A skill that can only fail on a condition
is not Stable.
```

---

## Notes for authors

- These two tables are **earned content**, not boilerplate — write each cell for the
  specific skill; delete rows that do not apply and add ones that do.
- A `references/<name>.md` depth file is earned, on-demand, knowledge-not-steps, and
  under ~200 lines (ENGINE-CONTRACTS section 12). Cite it by exact path so it
  resolves on disk (C1).
- A dispatched-leaf agent (`agents/<name>.md`) reuses the SAME `## Capability
  routing` block and adds a machine-parseable `## Output contract` — see
  `agents/_TEMPLATE.md`.
