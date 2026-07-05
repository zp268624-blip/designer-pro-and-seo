# Capability Tiers — the tool-aware routing contract

Every skill that *can* use an external capability (web crawling, SERP/keyword
data, backlinks, image generation, browser QA, competitive research) routes
through the **same four-tier cascade**. The skill adapts to whatever is available
in the user's session instead of hard-depending on any one paid tool.

This is the plugin's core promise restated operationally: **the free/built-in path
is the product; dedicated tools only deepen it; nothing ever just fails.**

---

## Why routing lives in skill instructions (not code)

There is **no supported API** for a skill or script to enumerate the MCP servers
connected in a Claude Code session. So MCP availability cannot be probed up front —
it is discovered by *trying*. The cascade is therefore written into each skill body
as a try-then-fallback chain:

> Attempt the dedicated tool (Tier 1). If the tool isn't exposed in the session, or
> the call errors, **follow the written fallback** — don't stop.

What *can* be detected from a script — CLI connectors on PATH and which API-key env
vars are set — is reported by `scripts/workflow/capability_probe.py`. Use it to
decide Tiers 3–4 and to tell the user what to install.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/capability_probe.py"            # JSON: {cli, env, notes}
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/capability_probe.py" --human    # ASCII summary
```

The probe never reads or prints secret *values* — only whether each key is set.

---

## The four tiers

| Tier | What | When it runs |
|---|---|---|
| **1 — Dedicated** | A purpose-built MCP/API (DataForSEO, Firecrawl, a GSC MCP, a paid image API) | The MCP tool is exposed in the session, or the API key is set. Try it first. |
| **2 — Built-in** | Claude's own tools (WebFetch, WebSearch, the bundled Playwright MCP) + this plugin's stdlib scripts | Tier 1 absent or errored. **This is the product** — it must produce a real, useful result on its own. |
| **3 — CLI connector** | A local CLI the user already has (e.g. `gemini` for image generation) | Tier 1–2 can't do it but `capability_probe` shows the CLI on PATH. |
| **4 — Guided prompt** | A manual checklist + concrete setup options + links | Nothing above is available. Never fail silently — hand the user a real manual path and name what to install to unlock a higher tier. |

**Always report which tier ran.** End every external-capability skill run with one
line, e.g. *"Source: Tier 2 (built-in WebFetch + tech_audit.py). Install a
DataForSEO MCP to add live keyword volume/CPC (Tier 1)."*

---

## Capability → tier map (seed rows)

The dedicated-tool column is *preferred-if-present*, never required.

| Capability | Tier 1 (dedicated) | Tier 2 (built-in / scripts) | Tier 3 (CLI) | Tier 4 (guided) |
|---|---|---|---|---|
| **Web crawl / scrape** | Firecrawl MCP | WebFetch + `html-extract`; `sitemap_tools.py` for coverage | — | manual fetch checklist + "add Firecrawl MCP" |
| **SERP / keywords** | DataForSEO MCP; a GSC MCP | WebSearch read (no volume/CPC) | — | "add DataForSEO for volume/difficulty" |
| **Backlinks** | Moz / Bing / DataForSEO MCP | WebSearch mention/linking-domain discovery (qualitative); fold in public web-graph data only if you have access | — | "add a link-data MCP for full profiles" |
| **Image generation** | nanobanana MCP / provider API key | — | `gemini` CLI image-gen | prompt to set a key or install the CLI, with options |
| **Browser / visual QA** | Playwright MCP | static a11y/structure checks via existing scripts | — | manual visual-QA checklist |
| **Competitive research** | Firecrawl MCP | WebFetch + WebSearch + `html-extract` | — | manual research checklist |
| **CWV field data** | Google CrUX/PSI (key) | `tech_audit.py` guidance (lab heuristics only) | — | "add a Google API key for field CWV" |

---

## Copy-paste skill section

Add this section to any skill that uses an external capability (place it after
`## Steps`, before `## Outputs`). Replace the bracketed parts for the skill's
capability; delete tiers that don't apply (e.g. drop Tier 3 if there's no CLI).

```markdown
## Capability routing

This skill follows the plugin's capability-tier cascade
(`references/CAPABILITY-TIERS.md`). It adapts to what's available and never fails:

1. **Tier 1 — [dedicated tool].** If [MCP/API] is available, use it for [what it adds].
2. **Tier 2 — built-in (the default).** Otherwise use [WebFetch/WebSearch/Playwright
   + which plugin script]. This produces [the real free-path result].
3. **Tier 3 — CLI connector.** If [`cli`] is on PATH (check `capability_probe.py`),
   use it for [what it adds].  *(omit if N/A)*
4. **Tier 4 — guided.** If none are available, deliver [the manual checklist] and
   name what to install to unlock a higher tier.

Always end by stating which tier ran and what a higher tier would add.
```

---

## Promotion note

A skill reworked onto this cascade ships **Stable** only when its **Tier 2 path is
fully specified and genuinely useful on its own** and it passes the promotion
checklist in `SHIPPING.md`. If a capability has no real built-in path (Tier 2 is
empty and only Tier 1/3 can do it), the skill stays **In development** and says so
honestly — the cascade is a promise, not a coat of paint.

---

## Capability families — the full tier map

Every external capability the plugin serves resolves through one of the families
below. The **slug** is the stable identifier a skill names in its routing block
(next section). The **Tier 2 column is THE PRODUCT** — it must produce a real,
shippable deliverable on its own; a family whose Tier 2 reads `—` cannot back a
`Stable` skill (the lone exception, `image-gen`, is exempt-by-spec and ships an
image-*spec* substitute instead of pixels).

The dedicated Tier-1 column is *preferred-if-present, never required*. Tier-2
backbone scripts land across the enrichment waves; where a script is not yet on
disk the built-in tool (WebFetch / WebSearch / Playwright) carries the family until
its script ships. A capability that spans two families embeds two routing blocks.

| Capability (slug) | Tier 1 — dedicated | Tier 2 — built-in + script **[PRODUCT]** | Tier 3 — local CLI | Tier 4 — guided |
|---|---|---|---|---|
| `web-crawl` | Firecrawl MCP (hosted/self-hosted) | WebFetch + `page_fetch.py` / `site_map.py`; sampled crawl states its boundary | — | manual fetch checklist + "add Firecrawl MCP" |
| `site-map` | Firecrawl MCP | `sitemap_tools.py` + `site_map.py` (robots + sitemap recursion → URL inventory) | — | "paste sitemap URL; add Firecrawl for JS sites" |
| `serp-keywords` | DataForSEO / Semrush MCP | WebSearch acquires the SERP blob → `serp_cluster.py` clusters it by SERP-overlap (deterministic offline post-processor over the orchestrator-supplied blob) | — | "add DataForSEO/Semrush for volume/CPC/difficulty" |
| `backlinks` | Moz / Bing / DataForSEO MCP | WebSearch mention + linking-domain discovery → qualitative referring-domain profile (optional public Common Crawl / Bing signals) | — | "add a link-data MCP for full referring-domain profiles" |
| `cwv-field` | Google PSI/CrUX (free key) | `cwv_check.py` lab heuristics + LCP<2.5 / CLS<0.1 / INP<200 targets (key-absent path is complete) | — | "set `CRUX_API_KEY`/`GOOGLE_API_KEY` for field CWV" |
| `indexation` | GSC MCP | `index_estimate.py` sitemap-vs-discoverable diff + GSC worksheet | — | "connect a GSC MCP for authoritative coverage" |
| `analytics` | GA4 (OAuth) | "what GA4/GSC would show" worksheet (never a synthesized number) | — | "connect GA4/GSC for organic traffic" |
| `local-maps` | DataForSEO / Google Places | `nap_check.py` + `geogrid.py` (SoLV math; free Overpass/Nominatim) | — | "add a maps MCP for live geo-grid rank tracking" |
| `competitive-research` | Firecrawl MCP | WebFetch + WebSearch + `html-extract` → scored comparison | — | manual research checklist |
| `visual-qa` | Playwright MCP | `a11y_static.py` structural a11y + token-contrast cross-check | — | manual visual-QA checklist |
| `schema` | — (built-in is canonical) | `schema_gen.py` generate/validate JSON-LD; `--graph-check` | — | n/a — Tier 2 is authoritative |
| `image-gen` | nanobanana MCP / provider key | **—** (C4-exempt-by-spec) → image **spec**: dimensions, alt, OG meta, schema `image` | `gemini` CLI image-gen | "set a provider key or install the `gemini` CLI" |

**Never-fabricate fields (emit a labeled proxy + a `needs_tier1` list, never a
synthesized number):** SERP volume/CPC/difficulty (`serp-keywords`), field CWV
(`cwv-field`), backlink/referring-domain counts (`backlinks`), indexed/excluded
page counts (`indexation`), GA4 traffic (`analytics`), review ratings
(`local-maps`). When only Tier 2 ran, the deliverable is still complete — it just
carries the proxy and names the tier that would harden it.

**Probe signals (what `capability_probe.py` can confirm up front).** MCP presence
is *not* probeable — it is discovered by trying (try Tier 1, follow the fallback on
error). What the probe reports is **CLI-on-PATH** and **env-var presence** (boolean
only, never the value): `DATAFORSEO_*`, `FIRECRAWL_API_KEY`, `FIRECRAWL_API_URL`,
`MOZ_API_KEY`, `BING_WEBMASTER_API_KEY`, `CRUX_API_KEY`, `GOOGLE_API_KEY`,
`GEMINI_API_KEY`. Use it to decide Tier 3/4 and to name what to install.

---

## The `## Capability routing` block — machine-parseable spec

The prose "Copy-paste skill section" above is for the human reading the skill. Its
**structured companion** is a fenced block with the info-string `capability-routing`
that the parity/free-path checks (`verify_release.py` C4) read mechanically. A skill
that uses any external capability embeds **one block per capability**.

**Placement (fixed):** the `## Capability routing` H2 goes **after `## Steps`,
before `## Outputs`** — the same slot ENGINE-CONTRACTS §1 reserves and §11 requires
of agents. The prose paragraph and the fenced block(s) both live under that one H2.

**Grammar:**
- Info string is exactly `capability-routing` (greppable; one fenced block per capability).
- One `key: value` per line; keys are lowercase `snake_case`; unknown keys are ignored; a missing **required** key is invalid.
- `none` is the explicit empty value for an absent tier; never leave a tier line blank.

```capability-routing
capability:   <slug from the family table, e.g. serp-keywords>
tier1:        <dedicated MCP/API, or none>
tier1_signal: <MCP tool to attempt | ENV_VAR (probe presence) | none>
tier2:        <built-in tool + backing script>     # REQUIRED, non-empty (see exemption)
tier2_yields: <the real free deliverable, one phrase>
tier3:        <local CLI, or none>
tier3_signal: <PATH binary checked by capability_probe.py, or none>
tier4:        <guided-setup deliverable + what to install to unlock a higher tier>
needs_tier1:  <comma-list of never-fabricate fields, or none>
```

**Field rules:**
- `tier2` MUST be non-empty and name a script that resolves on disk and is exercised
  by a golden example (C4 reuses the `check_refs` resolver). **Exemption:**
  `seo-image-gen` sets `tier2: image-spec substitute (dimensions, alt, OG, schema image)`
  plus `c4_exempt: true`; its description must not imply a free pixel path.
- `tier1_signal` / `tier3_signal` carry only what the probe can confirm (env-var
  presence or CLI-on-PATH). MCP availability is **not** a signal — it is tried, not probed.
- `needs_tier1` lists the never-fabricate fields for this capability; when only
  Tier 2 ran, the skill emits these as labeled proxies + this list, never a number.
- Drop the `tier3*` lines (set `none`) when no CLI serves the capability.

**Worked example** (`seo-backlinks`, between its Steps and Outputs):

```capability-routing
capability:   backlinks
tier1:        Moz / Bing / DataForSEO MCP
tier1_signal: MOZ_API_KEY | BING_WEBMASTER_API_KEY | DATAFORSEO_USERNAME
tier2:        WebSearch mention + linking-domain discovery -> qualitative referring-domain profile
tier2_yields: qualitative referring-domain + anchor read + prospect list (no exact counts/authority), zero spend
tier3:        none
tier3_signal: none
tier4:        manual link-prospecting checklist; add a link-data MCP for full profiles
needs_tier1:  referring-domain count, backlink count, domain authority score
```

End the run as always: state which tier ran and what a higher tier would add.
