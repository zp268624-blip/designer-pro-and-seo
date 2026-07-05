#!/usr/bin/env python3
"""
capability_probe.py — detect which optional capabilities are available, so a skill
can route through the plugin's capability-tier cascade (see
references/CAPABILITY-TIERS.md) instead of hard-depending on any one tool.

It reports two things it CAN honestly detect from a script:
  - CLI connectors on PATH (e.g. `gemini`, `node`, `npx`, `codex`)
  - relevant environment variables being SET (presence only — never their value)

It deliberately does NOT try to detect connected MCP servers: there is no
supported API for a script (or a skill) to enumerate the MCP tools exposed in a
Claude Code session. MCP availability is handled inside skill instructions as a
try-then-fallback chain (Tier 1 attempts the dedicated tool; on absence or error
the skill follows the written fallback). This probe informs Tiers 3-4 (CLI
connectors and the guided prompt) and surfaces which API keys are configured.

Security: this script reads environment variables but only ever records whether
each is SET (a boolean). It never prints, logs, or returns a secret value.

Output: machine-readable JSON by default; `--human` prints an ASCII-only summary
(safe on a Windows cp1252 console). Always exits 0 — availability is information,
not failure.

Usage:
  python3 capability_probe.py
  python3 capability_probe.py --human
  python3 capability_probe.py --env MY_PROVIDER_KEY,OTHER_KEY   # also check these
"""
import argparse
import json
import os
import shutil
import sys

# CLI connectors the plugin can route to when present.
DEFAULT_CLIS = ["gemini", "node", "npx", "codex", "python3", "py", "git"]

# Env vars that unlock paid/optional tiers. Presence is reported; values never are.
DEFAULT_ENV_VARS = [
    "DATAFORSEO_USERNAME",
    "DATAFORSEO_PASSWORD",
    "FIRECRAWL_API_KEY",
    "FIRECRAWL_API_URL",
    "MOZ_API_KEY",
    "BING_WEBMASTER_API_KEY",
    "CRUX_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
]

# Capability families (references/CAPABILITY-TIERS.md). Each row maps a capability
# slug to its Tier-1->Tier-4 cascade. The probe can only confirm two signals:
#   - tier1_signals: env-var names whose PRESENCE (boolean) unlocks the dedicated tier
#   - tier3_signal:  a CLI name on PATH that serves the capability (or None)
# MCP availability is NOT probeable (discovered by trying at run time), so a family
# whose only Tier-1 path is an MCP carries an empty tier1_signals list -- its row
# still names Tier 1 for guidance but the probe cannot mark it available.
# tier2 is THE PRODUCT: available by default (a stdlib/built-in path), except the
# spec-exempt image-gen family whose Tier 2 ships an image *spec*, not pixels.
CAPABILITY_FAMILIES = [
    {"slug": "web-crawl",
     "tier1": "Firecrawl MCP", "tier1_signals": ["FIRECRAWL_API_KEY", "FIRECRAWL_API_URL"],
     "tier2": "WebFetch + page_fetch.py / site_map.py", "tier2_available": True,
     "tier3": None, "tier3_signal": None,
     "tier4": "manual fetch checklist; add Firecrawl MCP"},
    {"slug": "site-map",
     "tier1": "Firecrawl MCP", "tier1_signals": ["FIRECRAWL_API_KEY", "FIRECRAWL_API_URL"],
     "tier2": "sitemap_tools.py + site_map.py", "tier2_available": True,
     "tier3": None, "tier3_signal": None,
     "tier4": "paste sitemap URL; add Firecrawl for JS sites"},
    {"slug": "serp-keywords",
     "tier1": "DataForSEO / Semrush MCP", "tier1_signals": ["DATAFORSEO_USERNAME", "DATAFORSEO_PASSWORD"],
     "tier2": "WebSearch SERP blob -> serp_cluster.py (deterministic SERP-overlap clustering)", "tier2_available": True,
     "tier3": None, "tier3_signal": None,
     "tier4": "add DataForSEO/Semrush for volume/CPC/difficulty"},
    {"slug": "backlinks",
     "tier1": "Moz / Bing / DataForSEO MCP",
     "tier1_signals": ["MOZ_API_KEY", "BING_WEBMASTER_API_KEY", "DATAFORSEO_USERNAME"],
     "tier2": "WebSearch mention + linking-domain discovery -> qualitative referring-domain profile", "tier2_available": True,
     "tier3": None, "tier3_signal": None,
     "tier4": "add a link-data MCP for full referring-domain profiles"},
    {"slug": "cwv-field",
     "tier1": "Google PSI / CrUX", "tier1_signals": ["CRUX_API_KEY", "GOOGLE_API_KEY"],
     "tier2": "cwv_check.py lab heuristics", "tier2_available": True,
     "tier3": None, "tier3_signal": None,
     "tier4": "set CRUX_API_KEY/GOOGLE_API_KEY for field CWV"},
    {"slug": "indexation",
     "tier1": "GSC MCP", "tier1_signals": [],
     "tier2": "index_estimate.py sitemap-vs-discoverable diff", "tier2_available": True,
     "tier3": None, "tier3_signal": None,
     "tier4": "connect a GSC MCP for authoritative coverage"},
    {"slug": "analytics",
     "tier1": "GA4 (OAuth)", "tier1_signals": [],
     "tier2": "GA4/GSC worksheet (never a synthesized number)", "tier2_available": True,
     "tier3": None, "tier3_signal": None,
     "tier4": "connect GA4/GSC for organic traffic"},
    {"slug": "local-maps",
     "tier1": "DataForSEO / Google Places",
     "tier1_signals": ["DATAFORSEO_USERNAME", "GOOGLE_API_KEY"],
     "tier2": "nap_check.py + geogrid.py (free Overpass/Nominatim)", "tier2_available": True,
     "tier3": None, "tier3_signal": None,
     "tier4": "add a maps MCP for live geo-grid rank tracking"},
    {"slug": "competitive-research",
     "tier1": "Firecrawl MCP", "tier1_signals": ["FIRECRAWL_API_KEY", "FIRECRAWL_API_URL"],
     "tier2": "WebFetch + WebSearch + html-extract", "tier2_available": True,
     "tier3": None, "tier3_signal": None,
     "tier4": "manual research checklist"},
    {"slug": "visual-qa",
     "tier1": "Playwright MCP", "tier1_signals": [],
     "tier2": "a11y_static.py structural a11y + token-contrast", "tier2_available": True,
     "tier3": None, "tier3_signal": None,
     "tier4": "manual visual-QA checklist"},
    {"slug": "schema",
     "tier1": None, "tier1_signals": [],
     "tier2": "schema_gen.py generate/validate JSON-LD", "tier2_available": True,
     "tier3": None, "tier3_signal": None,
     "tier4": "n/a -- Tier 2 is authoritative"},
    {"slug": "image-gen",
     "tier1": "nanobanana MCP / provider key", "tier1_signals": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
     "tier2": "image-spec substitute (dimensions, alt, OG, schema image)", "tier2_available": False,
     "tier3": "gemini CLI image-gen", "tier3_signal": "gemini",
     "tier4": "set a provider key or install the gemini CLI"},
]


def probe_clis(clis=None):
    """Return {name: bool} for each CLI, True when found on PATH.

    shutil.which resolves PATHEXT on Windows (.exe/.cmd/.bat), so an npm-installed
    `gemini.cmd` is detected the same as a POSIX `gemini`.
    """
    clis = DEFAULT_CLIS if clis is None else clis
    return {str(name): shutil.which(str(name)) is not None for name in clis}


def probe_env(env_vars=None):
    """Return {name: bool} for each env var, True when set to a non-empty value.

    Only the boolean is produced — the secret value is never read into the result,
    printed, or returned.
    """
    env_vars = DEFAULT_ENV_VARS if env_vars is None else env_vars
    return {str(name): bool(os.environ.get(str(name))) for name in env_vars}


def build_capabilities(cli, env):
    """Map detected CLIs + env-var presence to the Tier-1->Tier-4 cascade per
    capability family (references/CAPABILITY-TIERS.md).

    For each family, a tier is `available` when the probe can CONFIRM its signal:
      - tier1: any of its tier1_signals env vars is set (boolean presence only),
      - tier2: it has a built-in/script path (the product; image-gen is exempt),
      - tier3: its tier3_signal CLI is on PATH.
    `active_tier` is the highest-priority available tier (1 > 2 > 3), else tier4 --
    the cascade never reports a dead end. MCP presence is NOT a signal (it is tried
    at run time), so an MCP-only Tier 1 stays unavailable here by design.
    """
    rows = []
    for fam in CAPABILITY_FAMILIES:
        t1_avail = any(bool(env.get(name)) for name in fam["tier1_signals"])
        t2_avail = bool(fam["tier2_available"])
        t3_signal = fam["tier3_signal"]
        t3_avail = bool(t3_signal) and bool(cli.get(t3_signal))
        if t1_avail:
            active = "tier1"
        elif t2_avail:
            active = "tier2"
        elif t3_avail:
            active = "tier3"
        else:
            active = "tier4"
        rows.append({
            "capability": fam["slug"],
            "tier1": {"label": fam["tier1"], "signals": list(fam["tier1_signals"]),
                      "available": t1_avail},
            "tier2": {"label": fam["tier2"], "available": t2_avail},
            "tier3": {"label": fam["tier3"], "signal": t3_signal, "available": t3_avail},
            "tier4": {"label": fam["tier4"]},
            "active_tier": active,
        })
    return rows


def build_report(clis=None, env_vars=None, budget=None, capabilities=False):
    cli = probe_clis(clis)
    env = probe_env(env_vars)
    notes = []

    if cli.get("gemini"):
        notes.append("gemini CLI available -- usable as an image-generation connector (Tier 3).")
    if not any(env.values()):
        notes.append(
            "No optional API keys detected -- skills run their free/built-in path "
            "(Tier 2) and name what a paid tool would add (Tier 4 guidance)."
        )
    notes.append(
        "MCP server connections are not detectable from this script; skills test "
        "for a dedicated MCP at run time and fall back per references/CAPABILITY-TIERS.md."
    )
    # "cli" stays first/always-present (the smoke test asserts it); "budget" is a
    # recorded passthrough (no behavior); "capabilities" is opt-in via --capabilities.
    report = {"cli": cli, "env": env, "notes": notes, "budget": budget}
    if capabilities:
        report["capabilities"] = build_capabilities(cli, env)
    return report


def format_human(report):
    """ASCII-only rendering — safe on a cp1252 console.

    The whole output is forced to ASCII at the end (non-ASCII bytes become '?'),
    so even a caller-supplied non-ASCII env-var name (via --env) can never raise
    UnicodeEncodeError when printed to a Windows console.
    """
    lines = ["Capability probe", "================", "", "CLI connectors (on PATH):"]
    for name, present in report["cli"].items():
        lines.append("  [%s] %s" % ("x" if present else " ", name))
    lines.append("")
    lines.append("Environment keys (set?):")
    for name, present in report["env"].items():
        lines.append("  [%s] %s" % ("x" if present else " ", name))
    if report.get("budget") is not None:
        lines.append("")
        lines.append("Budget (passthrough): %s" % report["budget"])
    if "capabilities" in report:
        lines.append("")
        lines.append("Capability cascade (active tier per family):")
        for row in report["capabilities"]:
            lines.append("  %-22s -> %s" % (row["capability"], row["active_tier"]))
    lines.append("")
    lines.append("Notes:")
    for note in report["notes"]:
        lines.append("  - " + note)
    text = "\n".join(lines)
    return text.encode("ascii", "replace").decode("ascii")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Detect optional CLI/env capabilities.")
    parser.add_argument("--human", action="store_true",
                        help="ASCII summary instead of JSON")
    parser.add_argument("--env", nargs="?", const="", default="",
                        help="comma-separated extra env-var names to also check")
    parser.add_argument("--capabilities", action="store_true",
                        help="also emit the Tier-1->Tier-4 cascade per capability family")
    parser.add_argument("--budget", nargs="?", const="", default=None,
                        help="passthrough budget label, recorded in output (no behavior)")
    # parse_known_args + tolerant flags keep the contract: always exit 0, never
    # crash on unexpected args (availability is information, not failure).
    args, _unknown = parser.parse_known_args(argv)

    env_vars = list(DEFAULT_ENV_VARS)
    if args.env:
        for extra in args.env.split(","):
            extra = extra.strip()
            if extra and extra not in env_vars:
                env_vars.append(extra)

    report = build_report(env_vars=env_vars, budget=args.budget,
                          capabilities=args.capabilities)

    if args.human:
        print(format_human(report))
    else:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
