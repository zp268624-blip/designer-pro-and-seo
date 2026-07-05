# Verify · Monitor the trend and close the loop back to Baseline

**Loop stage:** Verify — measure whether the plan is compounding, then start the next cycle.
**When to run:** at the end of each cycle, across the accumulated snapshots.

A single diff proves one change; a trend proves a *strategy*. This prompt reads the
regression timeline and local visibility, decides whether the plan is compounding, and —
the point of the whole loop — hands the current state back to Baseline as the next cycle's
starting line.

## Evidence to gather (free Tier-2)

- `scripts/seo/drift_history.py` — enumerates stored baselines and runs the severity
  engine on each consecutive snapshot pair to emit a regression timeline (per-transition
  changed-count + critical/high/advisory tally). Offline; no capture, no network.
- `scripts/seo/geogrid.py` — Share-of-Local-Voice over an N x N geo-grid for local
  engagements: reciprocal-rank visibility, coverage %, top-3 %, avg found rank. It never
  fabricates (a never-found point scores 0); only `--geocode` touches the network, via the
  shared SSRF guard. See `references/seo-local-unified/solv-geogrid-formula.md`.

`needs_tier1`: organic traffic, impressions, clicks, and position history are
never-fabricate fields — track element/health/SoLV trends on the free path and present the
GSC/GA4 view as a `needs_tier1` worksheet (never a synthesized number).

## The prompt

> Assess whether the plan is compounding for {domain}. Read the drift trend across the
> cycle's snapshots — are critical/high changes trending down and intended changes
> sticking? For a local engagement, report the SoLV geo-grid movement (coverage, top-3,
> avg rank) versus the prior cycle. Judge each roadmap task against the metric it carried:
> moved / flat / regressed. State which outcomes the free path proved and which need a
> GSC/GA4 connector (list them as a `needs_tier1` worksheet, not numbers). Then produce the
> **next cycle's opening measurement**: promote the current snapshot to the new Baseline
> label and name the top carried-over and newly-surfaced candidates. Do not assert
> traffic/ranking gains the free tier cannot observe.

## Decision it drives

- **Is the strategy working** — which metrics moved, which did not, what to double down on.
- **The next cycle's Baseline** — the loop closes and compounds instead of resetting.

## Hand off to

- `baseline/` — the promoted snapshot is the next cycle's starting line (same drift engine,
  which is what makes the loop a loop).
- `prioritize/` — carried-over and newly-surfaced candidates seed the next backlog.
