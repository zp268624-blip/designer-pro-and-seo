#!/usr/bin/env python3
"""
crawl_inventory.py -- classify a list of discovered URLs into a structured
inventory (page-type buckets, crawl depth, per-bucket counts).

This is the deterministic post-processor over a crawl/site-map step: a discovery
tool (e.g. site_map.py, a sitemap, or Firecrawl) hands over the raw URL list, and
this script turns it into the inventory the seo-audit socket reasons about -- how
many products vs. blog posts vs. legal pages, how deep the site goes, how many
hosts. It does NOT fetch anything; it only parses the URLs it is given (offline).

Page-type buckets are assigned by URL-path heuristics in a fixed precedence order,
so the same input always yields the same inventory. Depth = number of non-empty
path segments (home = 0).

Input via --urls FILE (or `--urls -` / no value -> stdin). The input may be:
  * newline-delimited URLs (blank lines and lines starting with # are ignored), or
  * a JSON array of URL strings, or
  * a JSON object with a "urls" list (e.g. site_map.py output).

Output: JSON to stdout by default; --human prints an ASCII summary. On bad input
(missing file, no parseable URLs) it prints a JSON error object and exits non-zero
-- never a raw traceback. Standard library only; deterministic.

Usage:
  py crawl_inventory.py --urls urls.txt
  py site_map.py ... | py crawl_inventory.py --urls -
  py crawl_inventory.py --urls inventory.json --human
"""
import argparse
import json
import sys
from urllib.parse import urlsplit


# (bucket, path-segment matchers). Checked in this fixed order; first hit wins.
# Each matcher is a set of path tokens; a URL lands in the bucket if any token
# appears as a path segment (or the path starts with it). "home" and "pagination"
# are handled separately.
BUCKET_RULES = [
    ("blog", ("blog", "news", "article", "articles", "post", "posts", "insights",
              "stories", "press")),
    ("product", ("product", "products", "shop", "store", "item", "items", "p")),
    ("category", ("category", "categories", "collection", "collections", "c",
                  "shop-all", "catalog")),
    ("location", ("location", "locations", "store-locator", "stores", "branches")),
    ("service", ("service", "services", "solutions", "what-we-do")),
    ("pricing", ("pricing", "plans", "price")),
    ("about", ("about", "about-us", "team", "company", "our-story", "careers",
               "jobs")),
    ("contact", ("contact", "contact-us", "support", "help", "get-in-touch")),
    ("legal", ("privacy", "privacy-policy", "terms", "terms-of-service", "tos",
               "legal", "cookie", "cookies", "disclaimer", "accessibility")),
    ("auth", ("login", "log-in", "signin", "sign-in", "signup", "sign-up",
              "register", "account", "my-account")),
    ("tag", ("tag", "tags", "topic", "topics")),
    ("author", ("author", "authors")),
    ("docs", ("docs", "documentation", "doc", "guide", "guides", "api", "kb",
              "knowledge-base", "faq", "faqs")),
]


def _extract_urls(text):
    """Return a list of URL strings from the raw input text. Accepts JSON
    (array / object-with-urls) or newline-delimited text."""
    stripped = text.strip()
    if stripped[:1] in ("[", "{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            return [str(u).strip() for u in data if str(u).strip()]
        if isinstance(data, dict):
            for key in ("urls", "inventory", "pages", "loc"):
                val = data.get(key)
                if isinstance(val, list):
                    out = []
                    for item in val:
                        if isinstance(item, str):
                            out.append(item.strip())
                        elif isinstance(item, dict):
                            for k in ("url", "loc", "href"):
                                if isinstance(item.get(k), str):
                                    out.append(item[k].strip())
                                    break
                    return [u for u in out if u]
    # newline-delimited fallback
    urls = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls


def _classify_url(url):
    """Return (bucket, depth) for one URL. Unrecognised hosts/paths -> ('other')."""
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    depth = len(segments)

    if depth == 0:
        return "home", 0

    # pagination is orthogonal to type; flag it explicitly so it doesn't masquerade
    # as a real content page.
    if "page" in segments or any(s.isdigit() for s in segments[-1:]) and \
            segments[-2:-1] == ["page"]:
        return "pagination", depth
    if "page" in (parts.query or ""):
        return "pagination", depth

    seg_set = set(s.lower() for s in segments)
    first = segments[0].lower()
    for bucket, tokens in BUCKET_RULES:
        token_set = set(tokens)
        if first in token_set or (seg_set & token_set):
            return bucket, depth

    return "other", depth


def build_inventory(urls):
    """Return the inventory dict for a list of URL strings. Deterministic."""
    buckets = {}
    samples = {}
    depth_dist = {}
    hosts = set()
    classified = []

    for url in urls:
        bucket, depth = _classify_url(url)
        buckets[bucket] = buckets.get(bucket, 0) + 1
        samples.setdefault(bucket, [])
        if len(samples[bucket]) < 5:
            samples[bucket].append(url)
        depth_dist[depth] = depth_dist.get(depth, 0) + 1
        host = urlsplit(url).netloc.lower()
        if host:
            hosts.add(host)
        classified.append({"url": url, "bucket": bucket, "depth": depth})

    return {
        "total": len(urls),
        "buckets": dict(sorted(buckets.items())),
        "samples": {k: samples[k] for k in sorted(samples)},
        "depth_distribution": {str(k): depth_dist[k] for k in sorted(depth_dist)},
        "max_depth": max(depth_dist) if depth_dist else 0,
        "hosts": sorted(hosts),
        "host_count": len(hosts),
    }


def _read_input(path):
    if path in (None, "-"):
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _format_human(inv):
    lines = ["Crawl inventory: %d URL(s), %d host(s), max depth %d"
             % (inv["total"], inv["host_count"], inv["max_depth"]), "  buckets:"]
    for bucket, count in sorted(inv["buckets"].items(),
                                key=lambda kv: (-kv[1], kv[0])):
        lines.append("    %-12s %d" % (bucket, count))
    lines.append("  depth distribution:")
    for depth, count in sorted(inv["depth_distribution"].items(),
                               key=lambda kv: int(kv[0])):
        lines.append("    depth %-3s %d" % (depth, count))
    text = "\n".join(lines)
    return text.encode("ascii", "replace").decode("ascii")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Bucket a discovered-URL list into a structured inventory.")
    ap.add_argument("--urls", nargs="?", default="-",
                    help="path to a URL list (text or JSON); '-' or omitted = stdin")
    ap.add_argument("--human", action="store_true", help="ASCII summary")
    args = ap.parse_args(argv)

    try:
        text = _read_input(args.urls)
    except FileNotFoundError:
        print(json.dumps({"error": "urls file not found: %s" % args.urls}))
        return 1
    except OSError as exc:
        print(json.dumps({"error": "could not read urls: %s" % exc}))
        return 1

    urls = _extract_urls(text)
    if not urls:
        print(json.dumps({"error": "no URLs found in input"}))
        return 1

    inv = build_inventory(urls)

    if args.human:
        print(_format_human(inv))
    else:
        print(json.dumps(inv, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
