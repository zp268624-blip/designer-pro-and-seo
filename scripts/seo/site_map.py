#!/usr/bin/env python3
"""
site_map.py -- robots.txt + sitemap discovery + on-page link harvest -> a
classified URL inventory (the free-first crawl backbone, W1a).

What it does (all stdlib, offline-friendly, deterministic):
  * parse robots.txt -- respects per-User-agent Disallow/Allow groups (longest-match
    wins, Allow breaks ties) and collects `Sitemap:` lines;
  * recurse sitemap.xml / a sitemap index (xml.etree, gzip-aware on fetch) into a
    flat URL list;
  * harvest on-page <a href> links (html.parser) and resolve them against a base URL;
  * classify every URL: internal vs external + a coarse page-type heuristic
    (home/article/product/category/about/contact/pricing/docs/tag/page);
  * emit an inventory with counts; flag URLs a robots Disallow group blocks.

Tiering (CAPABILITY-TIERS.md): this is the Tier-2 free path. A full crawl needs a
Tier-1 connector (Firecrawl/DataForSEO); the `--sample N` SAMPLED mode fetches only
a priority subset and STATES its sampling boundary in the output
("fetched N of M inventoried URLs; full crawl needs Tier-1") so degradation is
visible. The free path is the product.

SSRF: per ENGINE-CONTRACTS.md S15, every fetch is gated by the shared
`validate_url()` guard (scripts/workflow/net_safety.py) -- imported as a local
sibling -- before any network call.

Output: JSON to stdout by default; `--human` prints an ASCII summary. Bad input
(no source, unreadable file, all-disallowed scheme) prints a JSON error object and
exits non-zero. Runs fully offline via `--file PATH` and/or `--no-network`.

Usage:
  # offline: parse a local sitemap or HTML page
  py site_map.py --file sitemap.xml --no-network
  py site_map.py --file page.html --base-url https://example.com/ --no-network
  py site_map.py --file page.html --base-url https://example.com/ --robots-file robots.txt --no-network
  # online: discover from a live site (robots + sitemap recursion + homepage links)
  py site_map.py --url https://example.com/
  # online sampled crawl (states the sampling boundary)
  py site_map.py --url https://example.com/ --sample 25
"""
import argparse
import gzip
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.error import URLError, HTTPError

# --- shared SSRF guard (local sibling in scripts/workflow) -------------------
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "workflow"))
from net_safety import (  # noqa: E402
    validate_url, safe_open, UrlValidationError, SafeFetchError,
)

UA = "Mozilla/5.0 (compatible; designer-pro-seo-sitemap/1.0)"
MAX_BYTES = 5_000_000          # hard cap on any single fetched body
MAX_SITEMAP_CHILDREN = 50      # bound recursion fan-out on a sitemap index


class FetchError(Exception):
    """A network/SSRF/read failure during a fetch. Carries an ASCII message."""


# --------------------------------------------------------------------------- #
# Pure helpers (offline, deterministic)                                        #
# --------------------------------------------------------------------------- #
def parse_sitemap(text):
    """Parse a sitemap (urlset) or sitemap index. Returns
    {'type': 'urlset'|'sitemapindex', 'urls': [loc, ...]}. Raises ValueError on
    XML that is not well-formed or not a recognised sitemap root."""
    try:
        root = ET.fromstring(text.strip())
    except ET.ParseError as exc:
        raise ValueError("not well-formed sitemap XML: %s" % exc)
    tag = root.tag.split("}")[-1]
    if tag not in ("urlset", "sitemapindex"):
        raise ValueError("unexpected sitemap root <%s> (want urlset/sitemapindex)" % tag)
    urls = []
    for loc in root.iter():
        if loc.tag.split("}")[-1] == "loc" and loc.text:
            u = loc.text.strip()
            if u:
                urls.append(u)
    # de-dupe preserving first-seen order (deterministic)
    seen, ordered = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            ordered.append(u)
    return {"type": tag, "urls": ordered}


class _HrefHarvester(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        for k, v in attrs:
            if k.lower() == "href" and v:
                self.hrefs.append(v.strip())


def harvest_links(html, base):
    """Extract <a href> links from HTML and resolve them against `base`. Keeps only
    http(s) links; drops mailto:/tel:/javascript:/pure-fragment links. De-duped,
    document order (deterministic)."""
    p = _HrefHarvester()
    try:
        p.feed(html)
    except Exception:
        # html.parser is lenient; never raise on malformed markup.
        pass
    out, seen = [], set()
    for href in p.hrefs:
        if not href or href.startswith("#"):
            continue
        low = href.lower()
        if low.startswith(("mailto:", "tel:", "javascript:", "data:")):
            continue
        resolved = urljoin(base or "", href)
        resolved = resolved.split("#", 1)[0]  # strip fragment
        if urlsplit(resolved).scheme not in ("http", "https"):
            continue
        if resolved and resolved not in seen:
            seen.add(resolved)
            out.append(resolved)
    return out


def _host(url):
    h = (urlsplit(url).hostname or "").lower()
    if h.startswith("www."):
        h = h[4:]
    return h


def is_internal(url, base):
    """True when `url`'s registrable-ish host matches `base`'s (www-insensitive).
    With no base, conservatively treats the URL as internal."""
    if not base:
        return True
    bh = _host(base)
    if not bh:
        return True
    return _host(url) == bh


_PAGE_TYPE_RULES = [
    ("article", (r"/blog(/|$)", r"/news(/|$)", r"/article", r"/post(s)?(/|$)", r"/insights(/|$)")),
    ("product", (r"/product(s)?(/|$)", r"/shop(/|$)", r"/item(s)?(/|$)", r"/p/")),
    ("category", (r"/categor(y|ies)(/|$)", r"/collection(s)?(/|$)", r"/tag(s)?(/|$)")),
    ("docs", (r"/docs(/|$)", r"/documentation(/|$)", r"/guide(s)?(/|$)")),
    ("pricing", (r"/pricing(/|$)", r"/plans(/|$)")),
    ("about", (r"/about", r"/team(/|$)", r"/company(/|$)")),
    ("contact", (r"/contact",)),
]


def classify_page_type(url):
    """Coarse, deterministic page-type heuristic from the URL path."""
    path = urlsplit(url).path or "/"
    if path in ("", "/"):
        return "home"
    low = path.lower()
    for label, patterns in _PAGE_TYPE_RULES:
        for pat in patterns:
            if re.search(pat, low):
                return label
    return "page"


# --------------------------------------------------------------------------- #
# robots.txt                                                                   #
# --------------------------------------------------------------------------- #
def parse_robots(text):
    """Parse robots.txt into {'sitemaps': [...], 'groups': [{'agents': [...],
    'rules': [(kind, pattern), ...]}]}. Comments stripped; case-insensitive
    directives. Deterministic order."""
    sitemaps, groups = [], []
    cur = None
    expecting_agent = False  # consecutive User-agent lines share the next ruleset
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, value = line.split(":", 1)
        field = field.strip().lower()
        value = value.strip()
        if field == "sitemap":
            if value and value not in sitemaps:
                sitemaps.append(value)
            continue
        if field == "user-agent":
            if cur is None or not expecting_agent:
                cur = {"agents": [], "rules": []}
                groups.append(cur)
            cur["agents"].append(value.lower())
            expecting_agent = True
            continue
        if field in ("disallow", "allow"):
            if cur is None:
                cur = {"agents": ["*"], "rules": []}
                groups.append(cur)
            expecting_agent = False
            cur["rules"].append((field, value))
    return {"sitemaps": sitemaps, "groups": groups}


def _pattern_to_re(pattern):
    """Translate a robots path pattern (* wildcard, $ end-anchor) to a regex."""
    out = ["^"]
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            out.append(".*")
        elif c == "$" and i == n - 1:
            out.append("$")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("".join(out))


def _group_for_agent(robots, agent):
    agent = agent.lower()
    fallback = None
    for g in robots["groups"]:
        if agent in g["agents"]:
            return g
        if "*" in g["agents"] and fallback is None:
            fallback = g
    return fallback


def robots_disallows(robots, path, agent="*"):
    """True when `path` is blocked for `agent` under the matching group. Longest
    matching directive wins; an Allow of equal-or-greater length beats a Disallow
    (Google's precedence). An empty Disallow value blocks nothing."""
    g = _group_for_agent(robots, agent)
    if not g:
        return False
    best_len, best_kind = -1, None
    for kind, pattern in g["rules"]:
        if pattern == "" and kind == "disallow":
            continue  # "Disallow:" with no value == allow everything
        if pattern == "" and kind == "allow":
            continue
        rx = _pattern_to_re(pattern)
        if rx.match(path):
            # match length = literal prefix length (ignore wildcard expansion)
            plen = len(pattern.replace("*", "").replace("$", ""))
            if plen > best_len or (plen == best_len and kind == "allow"):
                best_len, best_kind = plen, kind
    return best_kind == "disallow"


def sampling_note(fetched, inventoried):
    """The exact, honest sampling-boundary statement for the Tier-2 sampled crawl."""
    return ("fetched %d of %d inventoried URLs; full crawl needs Tier-1"
            % (fetched, inventoried))


# --------------------------------------------------------------------------- #
# Fetch (SSRF-guarded)                                                         #
# --------------------------------------------------------------------------- #
def fetch(url, timeout=10):
    """SSRF-guarded GET via the shared net_safety.safe_open, which validates the start
    URL and EVERY redirect hop before fetching it (no auto-followed, unvalidated
    redirect). Gunzips when needed, caps the body. Raises FetchError (ASCII message) on
    any failure. NEVER called when --no-network is set."""
    try:
        resp, chain = safe_open(url, timeout=timeout, headers={"User-Agent": UA})
    except UrlValidationError as exc:
        raise FetchError("blocked url: %s" % exc)
    except SafeFetchError as exc:
        raise FetchError("redirect rejected: %s" % exc)
    except (URLError, HTTPError, ValueError, TimeoutError, OSError) as exc:
        raise FetchError("fetch failed: %s" % exc)
    try:
        status = getattr(resp, "status", None) or getattr(resp, "code", None)
        if status is not None and status >= 400:
            raise FetchError("fetch failed: HTTP %s" % status)
        raw = resp.read(MAX_BYTES)
        enc = (resp.headers.get("Content-Encoding") or "").lower()
        final_url = chain[-1]["url"] if chain else url
        if "gzip" in enc or final_url.endswith(".gz"):
            try:
                raw = gzip.decompress(raw)
            except (OSError, EOFError):
                pass
        return raw.decode("utf-8", "replace")
    except (URLError, HTTPError, ValueError, TimeoutError, OSError) as exc:
        raise FetchError("fetch failed: %s" % exc)
    finally:
        try:
            resp.close()
        except Exception:
            pass


def discover_from_url(url, report, sample=None, timeout=10):
    """Online discovery: robots.txt -> sitemap recursion -> homepage link harvest.
    Mutates `report`. Each fetch is SSRF-guarded inside fetch(). Returns
    (base, robots, inventoried, fetch_stats) where fetch_stats is {'ok': n, 'fail': n}
    counting successful vs failed/SSRF-blocked discovery fetches -- so run() can tell an
    all-fetches-failed crawl (empty inventory => hard error) apart from a reachable but
    genuinely empty site. A parse failure on a fetched body is NOT a fetch failure (the
    fetch succeeded); only a FetchError counts against 'fail'."""
    split = urlsplit(url)
    base = "%s://%s/" % (split.scheme, split.netloc)
    report["base_url"] = base
    stats = {"ok": 0, "fail": 0}

    # 1. robots.txt
    robots = {"sitemaps": [], "groups": []}
    try:
        robots_txt = fetch(urljoin(base, "/robots.txt"), timeout)
        stats["ok"] += 1
        robots = parse_robots(robots_txt)
        report["robots"] = {"sitemaps": robots["sitemaps"],
                            "group_count": len(robots["groups"])}
    except FetchError as exc:
        stats["fail"] += 1
        report["warnings"].append("robots.txt unavailable (%s)" % exc)

    # 2. sitemaps: those robots names, else the conventional /sitemap.xml
    sitemap_urls = list(robots["sitemaps"]) or [urljoin(base, "/sitemap.xml")]
    inventoried, sitemaps_seen = [], []
    for sm_url in sitemap_urls:
        try:
            sm_text = fetch(sm_url, timeout)
            stats["ok"] += 1
        except FetchError as exc:
            stats["fail"] += 1
            report["warnings"].append("sitemap %s skipped (%s)" % (sm_url, exc))
            continue
        try:
            parsed = parse_sitemap(sm_text)
        except ValueError as exc:
            report["warnings"].append("sitemap %s skipped (%s)" % (sm_url, exc))
            continue
        sitemaps_seen.append(sm_url)
        if parsed["type"] == "sitemapindex":
            for child in parsed["urls"][:MAX_SITEMAP_CHILDREN]:
                try:
                    child_text = fetch(child, timeout)
                    stats["ok"] += 1
                except FetchError as exc:
                    stats["fail"] += 1
                    report["warnings"].append("child sitemap %s skipped (%s)" % (child, exc))
                    continue
                try:
                    child_parsed = parse_sitemap(child_text)
                except ValueError as exc:
                    report["warnings"].append("child sitemap %s skipped (%s)" % (child, exc))
                    continue
                sitemaps_seen.append(child)
                inventoried.extend(("sitemap", u) for u in child_parsed["urls"])
        else:
            inventoried.extend(("sitemap", u) for u in parsed["urls"])

    # 3. homepage on-page links
    try:
        homepage = fetch(url, timeout)
        stats["ok"] += 1
        for u in harvest_links(homepage, base):
            inventoried.append(("link", u))
    except FetchError as exc:
        stats["fail"] += 1
        report["warnings"].append("homepage link harvest skipped (%s)" % exc)

    report["sitemaps_discovered"] = sitemaps_seen
    return base, robots, inventoried, stats


# --------------------------------------------------------------------------- #
# Inventory assembly                                                           #
# --------------------------------------------------------------------------- #
def build_inventory(pairs, base, robots, sample=None, fetched_count=0):
    """pairs: list of (source, url). Returns (inventory, counts, sampling-or-None).
    De-dupes by URL (keeping first source), classifies, flags robots-disallowed."""
    seen, inventory = set(), []
    for source, url in pairs:
        if url in seen:
            continue
        seen.add(url)
        internal = is_internal(url, base)
        path = urlsplit(url).path or "/"
        disallowed = bool(internal and robots and robots.get("groups")
                          and robots_disallows(robots, path))
        inventory.append({
            "url": url,
            "internal": internal,
            "page_type": classify_page_type(url),
            "source": source,
            "disallowed": disallowed,
        })
    inventory.sort(key=lambda it: it["url"])  # deterministic

    counts = {
        "total": len(inventory),
        "internal": sum(1 for it in inventory if it["internal"]),
        "external": sum(1 for it in inventory if not it["internal"]),
        "disallowed": sum(1 for it in inventory if it["disallowed"]),
        "by_page_type": {},
        "by_source": {},
    }
    for it in inventory:
        counts["by_page_type"][it["page_type"]] = counts["by_page_type"].get(it["page_type"], 0) + 1
        counts["by_source"][it["source"]] = counts["by_source"].get(it["source"], 0) + 1

    sampling = None
    if sample is not None:
        sampling = {
            "requested": sample,
            "inventoried": len(inventory),
            "fetched": fetched_count,
            "boundary": "sampled",
            "note": sampling_note(fetched_count, len(inventory)),
        }
    return inventory, counts, sampling


# --------------------------------------------------------------------------- #
# Offline file handling                                                        #
# --------------------------------------------------------------------------- #
def _detect_and_parse_file(text):
    """Return (source_type, payload). source_type in
    {'sitemap','html','robots'}."""
    stripped = text.lstrip()
    low = stripped.lower()
    # XML sitemap?
    if low.startswith("<?xml") or "<urlset" in low or "<sitemapindex" in low:
        try:
            return "sitemap", parse_sitemap(text)
        except ValueError:
            pass
    # HTML?
    if "<html" in low or "<!doctype html" in low or "<a " in low or "<body" in low:
        return "html", text
    # robots.txt heuristic
    if re.search(r"(?im)^\s*(user-agent|disallow|allow|sitemap)\s*:", text):
        return "robots", parse_robots(text)
    # default: try sitemap, else treat as html
    try:
        return "sitemap", parse_sitemap(text)
    except ValueError:
        return "html", text


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def run(args):
    """Build the report dict and return (report, exit_code)."""
    report = {
        "target": args.url or args.file,
        "mode": None,
        "source_type": None,
        "base_url": args.base_url or None,
        "robots": {},
        "sitemaps_discovered": [],
        "inventory": [],
        "counts": {},
        "warnings": [],
        "errors": [],
    }

    # robots supplied offline (applies in --file mode)
    robots = {"sitemaps": [], "groups": []}
    if args.robots_file:
        try:
            with open(args.robots_file, encoding="utf-8", errors="replace") as fh:
                robots = parse_robots(fh.read())
            report["robots"] = {"sitemaps": robots["sitemaps"],
                                "group_count": len(robots["groups"])}
        except OSError as exc:
            report["errors"].append("could not read --robots-file: %s" % exc)
            return report, 1

    # ---- offline file mode ----
    if args.file:
        report["mode"] = "offline-file"
        try:
            with open(args.file, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            report["errors"].append("could not read --file: %s" % exc)
            return report, 1
        try:
            source_type, payload = _detect_and_parse_file(text)
        except ValueError as exc:
            report["errors"].append("could not parse --file: %s" % exc)
            return report, 1
        report["source_type"] = source_type
        base = args.base_url or None
        pairs = []
        if source_type == "sitemap":
            if base is None and payload["urls"]:
                base = "%s://%s/" % (urlsplit(payload["urls"][0]).scheme,
                                     urlsplit(payload["urls"][0]).netloc)
                report["base_url"] = base
            src = "sitemap-index" if payload["type"] == "sitemapindex" else "sitemap"
            pairs = [(src, u) for u in payload["urls"]]
            if payload["type"] == "sitemapindex":
                report["sitemaps_discovered"] = list(payload["urls"])
                report["warnings"].append(
                    "sitemap index: %d child sitemaps listed; offline mode does not "
                    "recurse them (re-run online or pass each child)" % len(payload["urls"]))
        elif source_type == "robots":
            robots = payload
            report["robots"] = {"sitemaps": robots["sitemaps"],
                                "group_count": len(robots["groups"])}
            pairs = [("sitemap", u) for u in robots["sitemaps"]]
        else:  # html
            pairs = [("link", u) for u in harvest_links(text, base or "")]

        inventory, counts, sampling = build_inventory(
            pairs, base, robots, sample=args.sample, fetched_count=0)
        report["inventory"], report["counts"] = inventory, counts
        if sampling is not None:
            report["sampling"] = sampling
        return report, 0

    # ---- online discovery mode ----
    if args.url:
        if args.no_network:
            report["errors"].append(
                "--no-network with --url and no --file: nothing to fetch. Pass --file "
                "for offline analysis.")
            return report, 1
        # validate up front so a bad/blocked URL is a clean JSON error, not a fetch crash
        try:
            validate_url(args.url, resolve=False)
        except ValueError as exc:
            report["errors"].append("invalid --url: %s" % exc)
            return report, 1
        report["mode"] = "sampled-crawl" if args.sample is not None else "url-discovery"
        report["source_type"] = "live-site"
        base, robots, pairs, fetch_stats = discover_from_url(
            args.url, report, sample=args.sample)
        report["base_url"] = base
        # sampled crawl: in this Tier-2 path we inventory live but only the
        # discovery fetches happen; a deeper per-URL crawl is Tier-1. fetched_count
        # reflects the discovery fetches already done (homepage + sitemaps).
        fetched = len(report.get("sitemaps_discovered", [])) + 1
        inventory, counts, sampling = build_inventory(
            pairs, base, robots, sample=args.sample, fetched_count=fetched)
        report["inventory"], report["counts"] = inventory, counts
        if sampling is not None:
            report["sampling"] = sampling
        if not inventory:
            # An EMPTY inventory whose ONLY outcomes were fetch/SSRF failures is a hard
            # error -- warnings must not let it slip through as exit 0. (A reachable but
            # genuinely empty site, where at least one fetch succeeded, still exits 0.)
            if fetch_stats["ok"] == 0 and fetch_stats["fail"] > 0:
                report["errors"].append(
                    "no URLs discovered: all %d discovery fetch(es) failed or were "
                    "SSRF-blocked" % fetch_stats["fail"])
                return report, 1
            if not report["warnings"]:
                report["errors"].append(
                    "no URLs discovered (empty robots/sitemap/homepage)")
                return report, 1
        return report, 0

    report["errors"].append("provide --url (online) or --file (offline)")
    return report, 1


def _format_human(report):
    lines = []
    lines.append("# SITEMAP / URL INVENTORY: %s" % report.get("target"))
    lines.append("mode=%s  source=%s  base=%s"
                 % (report.get("mode"), report.get("source_type"), report.get("base_url")))
    c = report.get("counts") or {}
    if c:
        lines.append("counts: total=%d internal=%d external=%d disallowed=%d"
                     % (c.get("total", 0), c.get("internal", 0),
                        c.get("external", 0), c.get("disallowed", 0)))
        if c.get("by_page_type"):
            lines.append("by page-type: " + ", ".join(
                "%s=%d" % (k, v) for k, v in sorted(c["by_page_type"].items())))
    rb = report.get("robots") or {}
    if rb.get("sitemaps"):
        lines.append("robots sitemaps: " + ", ".join(rb["sitemaps"]))
    if report.get("sampling"):
        lines.append("SAMPLING: " + report["sampling"]["note"])
    for it in report.get("inventory", [])[:50]:
        flag = " [DISALLOWED]" if it.get("disallowed") else ""
        scope = "int" if it.get("internal") else "ext"
        lines.append("  [%s/%s] %s%s" % (scope, it.get("page_type"), it.get("url"), flag))
    if len(report.get("inventory", [])) > 50:
        lines.append("  ... (%d more)" % (len(report["inventory"]) - 50))
    for w in report.get("warnings", []):
        lines.append("[WARN] " + w)
    for e in report.get("errors", []):
        lines.append("[ERROR] " + e)
    text = "\n".join(lines)
    return text.encode("ascii", "replace").decode("ascii")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="robots + sitemap discovery + on-page link harvest -> URL inventory")
    ap.add_argument("--url", help="live site URL (online discovery)")
    ap.add_argument("--file", help="local sitemap.xml or HTML file (offline)")
    ap.add_argument("--robots-file", dest="robots_file",
                    help="local robots.txt to apply offline (Disallow + Sitemap lines)")
    ap.add_argument("--base-url", dest="base_url", default="",
                    help="base URL for resolving/classifying links in --file mode")
    ap.add_argument("--sample", type=int, default=None,
                    help="SAMPLED crawl: states 'fetched N of M ...' boundary")
    ap.add_argument("--no-network", action="store_true", help="never fetch")
    ap.add_argument("--human", action="store_true", help="ASCII summary instead of JSON")
    args = ap.parse_args(argv)

    if args.base_url == "":
        args.base_url = None

    report, code = run(args)
    if code != 0 and report.get("errors"):
        # surface a single top-level error string for callers that key off it,
        # while keeping the full errors[] list.
        report["error"] = report["errors"][0]
    if args.human:
        print(_format_human(report))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
