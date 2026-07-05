---
# Required frontmatter for a dispatched-leaf agent (ENGINE-CONTRACTS section 11).
# Fill every field; delete the guidance comments when you author a real agent.
name: <kebab-case; MUST equal the sibling skill folder this agent wraps>
description: <one line — what this dispatched leaf does + the capability/orchestrator that fans out to it. Describe the dispatch relationship in prose only; an agent has no Dependencies edge and never names its orchestrator as one.>
model: sonnet            # leaf default. haiku for a trivial script-runner; opus only if the leaf truly reasons.
maxTurns: 12             # hard ceiling. A leaf is bounded — pick the smallest turn budget that still completes.
tools: Read, Glob, Grep  # LEAST PRIVILEGE (C5): list ONLY the tools the wrapped method uses.
                         #   add Bash ONLY if it runs a bundled script; add Write ONLY if it emits a file.
                         #   a fetch-only agent gets NO Bash/Write; never grant Task (agents never call agents);
                         #   never grant WebSearch/WebFetch when a Bash script already does the fetch.
---

# <name>  (dispatched-leaf agent)

<!-- WHAT THIS FILE IS: a real Agent-tool subagent an orchestrator fans out to in
     parallel. It is a LEAF — it runs a method and returns a structured result; it
     does not dispatch anything. Author an agent ONLY for a dispatched leaf, NEVER
     for an orchestrator. -->
<!-- NO FORKED METHOD: this agent wraps the SAME method as its sibling skill —
     same Tier cascade, same free path, same outputs. One behavior, two entry
     points (skill = inline, agent = dispatched). Do not re-implement or "improve"
     the skill's logic here. -->
<!-- DAG (ENGINE-CONTRACTS section 4): orchestrator -> agent -> script, one
     direction. Agents never call agents. A specialist never lists its orchestrator
     as a dependency. A mutual relationship is a prose cross-reference, never an edge. -->

**Wraps:** `skills/<name>/SKILL.md` — same method, no forked logic.

## Method

<!-- One short paragraph + the exact bundled-script invocation the sibling skill
     uses. Keep it a pointer to the skill, not a re-statement of every step. -->

Run the sibling skill's method, e.g.:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<dir>/<script>.py" --<args>   # same call the skill makes
```

## Capability routing

<!-- REQUIRED block 1 (ENGINE-CONTRACTS section 11). Same contract as the optional
     skill section in CAPABILITY-TIERS.md. Prose for the human, then ONE fenced
     `capability-routing` block per capability the agent serves. The agent must
     obey the SAME cascade as its skill — never fail; Tier 2 is the product. -->

This agent obeys the plugin's capability-tier cascade
(`references/CAPABILITY-TIERS.md`), identical to the skill it wraps. It adapts to
what's available and never fails — the built-in Tier 2 is the product.

1. **Tier 1 — <dedicated MCP/API>.** If available, use it for <what it adds>.
2. **Tier 2 — built-in (the default).** Otherwise run <built-in tool + bundled
   script>. This is the complete free deliverable.
3. **Tier 3 — <local CLI>.** *(set `none` and drop if no CLI serves this.)*
4. **Tier 4 — guided.** If nothing above is available, deliver <manual checklist>
   and name what to install to unlock a higher tier.

End by stating which tier ran and what a higher tier would add. Never fabricate a
never-fabricate field — emit a labeled proxy + the `needs_tier1` list instead.

<!-- The machine-parseable companion. Info string is EXACTLY `capability-routing`.
     One `key: value` per line; lowercase snake_case keys; `none` is the explicit
     empty value (never blank). `tier2` is REQUIRED and must name a script that
     resolves on disk and is exercised by a golden example (C4). -->

```capability-routing
capability:   <slug from the CAPABILITY-TIERS family table>
tier1:        <dedicated MCP/API, or none>
tier1_signal: <MCP tool to attempt | ENV_VAR (probe presence) | none>
tier2:        scripts/<dir>/<script>.py (<built-in tool + what it computes>)
tier2_yields: <the real free deliverable, one phrase>
tier3:        <local CLI, or none>
tier3_signal: <PATH binary capability_probe.py confirms, or none>
tier4:        <guided-setup deliverable + what to install to unlock a higher tier>
needs_tier1:  <comma-list of never-fabricate fields, or none>
```

## Output contract

<!-- REQUIRED block 2 (ENGINE-CONTRACTS section 11). A machine-parseable, fixed-key
     block so the orchestrator can fan-in deterministically. State which tier ran
     (`tier_ran`) and surface any `needs_tier1`. NEVER emit a fabricated number —
     a never-fabricate field ships as a labeled proxy + the needs_tier1 list.
     The FIVE universal keys `agent, status, tier_ran, needs_tier1, tier_line` are
     REQUIRED of every agent (C3 enforces them: deterministic fan-in + honest tier
     reporting). The rest (`target, findings, score, handoffs`, and any others) are
     OPTIONAL, agent-specific — keep, drop, or add per what the method produces. -->

The agent returns exactly this block (one `key: value` per line; complex values are
inline JSON) so a parent can aggregate many leaves without re-parsing prose:

```output-contract
agent:        <name>                 # REQUIRED
status:       ok | partial | error   # REQUIRED
tier_ran:     1 | 2 | 3 | 4           # REQUIRED
needs_tier1:  <never-fabricate fields emitted as proxies, or none>   # REQUIRED
tier_line:    <one sentence: which tier ran + what a higher tier would add>   # REQUIRED
target:       <the URL / file / subject analyzed>                    # optional (agent-specific)
findings:     <JSON array of {field, severity, finding, fix}; severity in critical|high|medium|info>   # optional
score:        <number, or null if the method does not score — never invent one>   # optional
handoffs:     <sibling specialists referenced in prose, or none>     # optional
```
