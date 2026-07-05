#!/usr/bin/env python3
"""serp_cluster.py -- SERP-overlap semantic clustering for content architecture.

The honest division of labour (clean-room + truth-in-advertising):
  * SERP ACQUISITION is a Claude / WebSearch (or DataForSEO / Semrush) step --
    NOT this script. Getting the top-ranked URLs for each keyword is the
    orchestrator's job.
  * THIS script is the DETERMINISTIC post-processor over an orchestrator-supplied
    SERP blob. It never fetches anything; it runs entirely offline.

Method (why SERP-overlap beats text/embedding similarity): if two keywords return
many of the SAME pages in Google's top results, Google already considers them the
same topic -- so one page can rank for both. That shared-result signal is the only
similarity that maps to "should these share a page?". Two keywords with identical
wording but disjoint SERPs are different topics; two worded-differently keywords
with the same SERP are one topic. See references/seo-cluster/serp-overlap-method.md.

Pipeline:
  1. Load the blob: JSON object {keyword: [ranked urls]} (top-N kept per keyword).
  2. Normalize URLs (drop scheme / www / trailing slash / query / fragment) so the
     same page counted twice is one page.
  3. Pairwise SERP-overlap = count of shared normalized URLs in the top-N.
  4. Cluster by single-linkage connected components over the chosen `--threshold`
     (minimum shared URLs to call two keywords the same topic).
  5. Assign roles: the most SERP-central keyword in each cluster is the pillar
     (hub); the rest are spokes. See references/seo-cluster/hub-and-spoke.md.
  6. Classify intent (informational / commercial / transactional / navigational)
     deterministically from keyword modifiers.
  7. Emit hub-and-spoke clusters + an internal-link matrix (anchor text per link).

Never fabricates volume / CPC / difficulty -- those are a Tier-1 (DataForSEO /
Semrush) deepener and ship as a `needs_tier1` list, never a synthesized number.

Output: JSON to stdout by default; `--human` prints an ASCII summary. Bad input ->
a JSON `{"error": ...}` object on stdout + a NON-ZERO exit (never a raw traceback).
Deterministic: same blob + same flags -> byte-identical output. stdlib only.

Usage:
  py serp_cluster.py --serps serps.json
  py serp_cluster.py --serps serps.json --threshold 3 --top 10 --human
  echo '{"kw":[ ... ]}' | py serp_cluster.py --serps -
"""
import argparse
import json
import re
import sys
import urllib.parse

DEFAULT_THRESHOLD = 3   # minimum shared top-N URLs to call two keywords one topic
DEFAULT_TOP_N = 10      # consider each keyword's top-N ranked URLs
MAX_SIBLING_LINKS = 3   # each spoke links to up to this many sibling spokes


class _JsonArgParser(argparse.ArgumentParser):
    """argparse's own failures (a missing required arg, a bad type/choice) must honor the
    JSON-error contract too: emit {"error": ...} to stdout + a non-zero exit, never a bare
    usage dump to stderr. stdlib + ASCII."""
    def error(self, message):
        msg = str(message).encode("ascii", "replace").decode("ascii")
        print(json.dumps({"error": msg}))
        sys.exit(2)

# --- deterministic intent classification ------------------------------------
# Ordered most-specific -> least; first family whose pattern hits wins. The order
# matters: "buy best X" is transactional (a purchase) before commercial-research.
_INTENT_RULES = [
    ("transactional", re.compile(
        r"\b(buy|order|purchase|cheap|cheapest|discount|coupon|deal|deals|"
        r"price|prices|pricing|cost|for sale|near me|book|booking|hire|"
        r"subscribe|signup|sign up|free shipping|in stock|quote)\b", re.I)),
    ("navigational", re.compile(
        r"\b(login|log in|sign in|account|dashboard|portal|download|"
        r"official site|official website|app store|contact)\b", re.I)),
    ("commercial", re.compile(
        r"\b(best|top|review|reviews|compare|comparison|vs|versus|"
        r"alternative|alternatives|cheapest|rated|ranking|ranked)\b", re.I)),
    ("informational", re.compile(
        r"\b(how|what|why|when|where|who|guide|tutorial|tips|ideas|examples?|"
        r"meaning|definition|explained|learn|tutorials?)\b", re.I)),
]


def classify_intent(keyword):
    """Return the search-intent family for a keyword, deterministically."""
    for label, pat in _INTENT_RULES:
        if pat.search(keyword):
            return label
    return "informational"  # the safe default for an unmodified head term


def normalize_url(url):
    """Collapse a SERP URL to a comparable page key: lowercase host (www stripped) +
    path (no trailing slash), dropping scheme / query / fragment. A scheme-less input
    ('site.com/c') is parsed as host+path too. Returns '' for an empty/garbage URL."""
    if not isinstance(url, str):
        return ""
    u = url.strip()
    if not u:
        return ""
    if "//" not in u and not u.lower().startswith(("http:", "https:")):
        u = "//" + u  # let urlsplit treat the leading token as the host
    parts = urllib.parse.urlsplit(u)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path or ""
    if len(path) > 1:
        path = path.rstrip("/")
    if path == "/":
        path = ""
    key = host + path
    return key


def _normalized_set(urls, top_n):
    """The set of normalized page keys for a keyword's top-N URLs (order preserved
    while taking the first top_n, then de-duplicated into a set for overlap math)."""
    out, seen = set(), 0
    for u in urls:
        if seen >= top_n:
            break
        seen += 1
        key = normalize_url(u)
        if key:
            out.add(key)
    return out


def _load_blob(arg):
    """Read the SERP blob from a file path or '-' (stdin). Returns the parsed object.
    Raises ValueError with an ASCII message on any read/parse/shape problem."""
    if arg == "-":
        raw = sys.stdin.read()
    else:
        try:
            with open(arg, encoding="utf-8") as f:
                raw = f.read()
        except OSError as exc:
            raise ValueError("could not read --serps file %r: %s" % (arg, exc))
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ValueError("--serps is not valid JSON: %s" % exc)
    if not isinstance(data, dict):
        raise ValueError(
            "--serps must be a JSON object {keyword: [ranked urls]}, got %s"
            % type(data).__name__)
    if not data:
        raise ValueError("--serps is an empty object; supply at least one keyword "
                         "with its ranked URLs")
    for kw, urls in data.items():
        if not isinstance(urls, list):
            raise ValueError("keyword %r maps to %s, expected a list of ranked URLs"
                             % (kw, type(urls).__name__))
    return data


def _components(keywords, shared, threshold):
    """Single-linkage connected components: keywords are one cluster when a chain of
    >=threshold-shared-URL edges connects them. Deterministic -- keywords are walked
    in sorted order and each component is returned sorted, so cluster identity does
    not depend on dict iteration order."""
    adj = {k: set() for k in keywords}
    for (a, b), n in shared.items():
        if n >= threshold:
            adj[a].add(b)
            adj[b].add(a)
    seen, comps = set(), []
    for start in keywords:  # already sorted by the caller
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            node = stack.pop()
            comp.append(node)
            for nb in sorted(adj[node]):
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        comps.append(sorted(comp))
    return comps


def _pillar(members, shared):
    """The cluster's hub = the most SERP-central keyword: highest summed shared-URL
    overlap with its siblings (it co-ranks with the most of them, so it is the
    broadest umbrella term). Ties break toward the shorter/headier term: fewer words,
    then fewer characters, then alphabetical -- fully deterministic."""
    def centrality(k):
        return sum(shared.get((min(k, o), max(k, o)), 0)
                   for o in members if o != k)
    return max(members, key=lambda k: (centrality(k), -len(k.split()), -len(k), _neg(k)))


def _neg(s):
    """A sort key that makes 'smaller alphabetical' win under max(): invert chars."""
    return tuple(-ord(c) for c in s)


def _sibling_links(spoke, others, shared):
    """Up to MAX_SIBLING_LINKS sibling spokes for `spoke`, chosen by shared-URL overlap
    (desc), tie-broken alphabetically -- the most topically-adjacent siblings."""
    ranked = sorted(
        others,
        key=lambda o: (-shared.get((min(spoke, o), max(spoke, o)), 0), o))
    return ranked[:MAX_SIBLING_LINKS]


def _bridge_member(spoke, members, shared, threshold):
    """The in-cluster member a BRIDGED spoke actually co-ranks with at >= threshold -- the
    single-linkage edge through which it joined the cluster (it does NOT co-rank with the
    pillar). Single-linkage guarantees at least one such neighbor exists. Highest overlap
    wins; ties break alphabetically -- fully deterministic."""
    cands = [(shared.get((min(spoke, m), max(spoke, m)), 0), m)
             for m in members if m != spoke]
    cands = [(n, m) for (n, m) in cands if n >= threshold]
    cands.sort(key=lambda t: (-t[0], t[1]))
    return cands[0][1] if cands else spoke


def cluster(blob, threshold=DEFAULT_THRESHOLD, top_n=DEFAULT_TOP_N):
    """Pure-function core: blob -> result dict. Importable + unit-testable."""
    keywords = sorted(blob.keys())
    sets = {k: _normalized_set(blob[k], top_n) for k in keywords}

    shared = {}
    for i in range(len(keywords)):
        for j in range(i + 1, len(keywords)):
            a, b = keywords[i], keywords[j]
            n = len(sets[a] & sets[b])
            if n:
                shared[(a, b)] = n

    comps = _components(keywords, shared, threshold)

    clusters, singletons = [], []
    cid = 0
    for members in comps:
        if len(members) < 2:
            kw = members[0]
            singletons.append({"keyword": kw, "intent": classify_intent(kw)})
            continue
        cid += 1
        pillar = _pillar(members, shared)
        spokes = [k for k in members if k != pillar]

        # Honesty fix: single-linkage can pull an end-of-chain member into the component
        # that shares FEWER than `threshold` URLs with the CHOSEN pillar. Such a member is
        # "bridged" -- it joined via a chain, not by co-ranking with the pillar -- so it
        # must NOT get a hub-and-spoke pillar link below threshold. Instead it links up to
        # its bridge (the neighbor it actually co-ranks with at >= threshold).
        bridge_of = {}
        for sp in spokes:
            if shared.get((min(sp, pillar), max(sp, pillar)), 0) < threshold:
                bridge_of[sp] = _bridge_member(sp, members, shared, threshold)

        links = []
        for sp in spokes:
            sh = shared.get((min(sp, pillar), max(sp, pillar)), 0)
            if sp not in bridge_of:  # DIRECT spoke: genuine >= threshold pillar link
                links.append({"from": sp, "to": pillar, "anchor": pillar,
                              "type": "spoke_to_pillar", "shared": sh})
                links.append({"from": pillar, "to": sp, "anchor": sp,
                              "type": "pillar_to_spoke", "shared": sh})
            else:                    # BRIDGED spoke: link up to its bridge, never the pillar
                br = bridge_of[sp]
                links.append({"from": sp, "to": br, "anchor": br,
                              "type": "spoke_to_bridge",
                              "shared": shared.get((min(sp, br), max(sp, br)), 0)})
        for sp in spokes:
            # Sibling candidates exclude self and (for a bridged spoke) its own bridge, so
            # an edge is never emitted twice.
            exclude = {sp, bridge_of.get(sp)}
            others = [s for s in spokes if s not in exclude]
            for sib in _sibling_links(sp, others, shared):
                links.append({
                    "from": sp, "to": sib, "anchor": sib,
                    "type": "spoke_to_sibling",
                    "shared": shared.get((min(sp, sib), max(sp, sib)), 0)})
        spoke_objs = []
        for sp in spokes:
            obj = {"keyword": sp, "intent": classify_intent(sp),
                   "shared_with_pillar": shared.get((min(sp, pillar), max(sp, pillar)), 0),
                   "bridged": sp in bridge_of}
            if sp in bridge_of:
                obj["links_via"] = bridge_of[sp]
            spoke_objs.append(obj)
        clusters.append({
            "id": cid,
            "pillar": pillar,
            "pillar_intent": classify_intent(pillar),
            "intent": classify_intent(pillar),  # cluster intent = the pillar's
            "size": len(members),
            "spokes": spoke_objs,
            "internal_links": links,
        })

    link_matrix = [dict(l, cluster=c["id"])
                   for c in clusters for l in c["internal_links"]]

    return {
        "params": {
            "threshold": threshold,
            "top_n": top_n,
            "keywords": len(keywords),
            "clusters": len(clusters),
            "singletons": len(singletons),
        },
        "clusters": clusters,
        "singletons": singletons,
        "link_matrix": link_matrix,
        "tier": ("Tier 2 (built-in serp_cluster.py over a WebSearch-acquired SERP "
                 "blob). Connect a DataForSEO / Semrush MCP for live bulk SERPs + "
                 "keyword volume / CPC / difficulty (Tier 1)."),
        "needs_tier1": ["keyword search volume", "CPC", "keyword difficulty"],
    }


def _format_human(result):
    lines = []
    p = result["params"]
    lines.append("SERP-overlap clusters (threshold=%d shared of top-%d URLs)"
                 % (p["threshold"], p["top_n"]))
    lines.append("  %d keywords -> %d cluster(s), %d singleton(s)"
                 % (p["keywords"], p["clusters"], p["singletons"]))
    for c in result["clusters"]:
        lines.append("")
        lines.append("Cluster %d  [%s]  (%d keywords)"
                     % (c["id"], c["intent"], c["size"]))
        lines.append("  PILLAR: %s" % c["pillar"])
        for s in c["spokes"]:
            if s.get("bridged"):
                lines.append("    - spoke: %s  [%s]  (bridged via %s; shares %d with pillar)"
                             % (s["keyword"], s["intent"], s.get("links_via"),
                                s["shared_with_pillar"]))
            else:
                lines.append("    - spoke: %s  [%s]  (shares %d URLs with pillar)"
                             % (s["keyword"], s["intent"], s["shared_with_pillar"]))
        lines.append("  Internal links:")
        for l in c["internal_links"]:
            arrow = {"spoke_to_pillar": "-> pillar",
                     "pillar_to_spoke": "-> spoke",
                     "spoke_to_sibling": "-> sibling",
                     "spoke_to_bridge": "-> bridge"}[l["type"]]
            lines.append("    %s %s %s  anchor=\"%s\""
                         % (l["from"], arrow, l["to"], l["anchor"]))
    if result["singletons"]:
        lines.append("")
        lines.append("Singletons (no >=threshold SERP overlap -- need more keywords "
                     "or data):")
        for s in result["singletons"]:
            lines.append("    - %s  [%s]" % (s["keyword"], s["intent"]))
    lines.append("")
    lines.append(result["tier"])
    lines.append("needs_tier1 (never fabricated): " + ", ".join(result["needs_tier1"]))
    text = "\n".join(lines)
    return text.encode("ascii", "replace").decode("ascii")


def main(argv=None):
    ap = _JsonArgParser(
        description="SERP-overlap semantic clustering over a supplied SERP blob "
                    "(offline post-processor; SERP acquisition is a separate step).")
    ap.add_argument("--serps", required=True,
                    help="path to a JSON object {keyword: [ranked urls]}, or '-' for stdin")
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                    help="min shared top-N URLs to cluster two keywords (default %d)"
                         % DEFAULT_THRESHOLD)
    ap.add_argument("--top", type=int, default=DEFAULT_TOP_N, dest="top_n",
                    help="consider each keyword's top-N ranked URLs (default %d)"
                         % DEFAULT_TOP_N)
    ap.add_argument("--human", action="store_true", help="ASCII summary instead of JSON")
    args = ap.parse_args(argv)

    if args.threshold < 1:
        print(json.dumps({"error": "--threshold must be >= 1"}))
        return 2
    if args.top_n < 1:
        print(json.dumps({"error": "--top must be >= 1"}))
        return 2

    try:
        blob = _load_blob(args.serps)
    except ValueError as exc:
        print(json.dumps({"error": str(exc).encode("ascii", "replace").decode("ascii")}))
        return 2

    result = cluster(blob, threshold=args.threshold, top_n=args.top_n)

    if args.human:
        print(_format_human(result))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
