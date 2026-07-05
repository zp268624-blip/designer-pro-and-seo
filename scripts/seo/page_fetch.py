#!/usr/bin/env python3
"""
page_fetch.py -- an SSRF-guarded single-URL fetcher (free-first backbone, W1a).

Fetches one URL and reports the final status, a useful header subset, content-type,
byte length, and the body (or a `--head` mode that issues a HEAD request and omits
the body). It follows the redirect chain with a max-hop cap and detects redirect
LOOPS, reporting the full chain either way.

SSRF is a contract, not a nicety: this script routes every fetch through the one
shared guard (`scripts/workflow/net_safety.safe_open`), which validates EVERY hop --
the start URL and each redirect target -- AND pins each connection to a validated IP
before fetching it, so a redirect (or a DNS rebind) to an internal IP / cloud-metadata
address is refused like a direct one.

A FLAG-GATED SPA-shell heuristic (`--detect-spa`, never default-on) inspects the
final HTML; when it looks like a client-rendered shell AND the network is available,
it MAY issue a second fetch with a different User-Agent to compare server output.
That UA-swap is always DISCLOSED in the output (performed true/false + both UA
strings) -- we never silently impersonate a different client.

Offline:
  --file PATH    read a local HTML file (no network; exits 0 on a readable file).
  --no-network   forbid any fetch (an error if a --url is given with no --file).

Output: JSON to stdout by default; `--human` prints an ASCII summary. Bad input
(missing/unreadable file, blocked/invalid URL, no input, fetch failure, redirect
loop, or hop cap exceeded) prints a JSON error object and exits non-zero -- never a
raw traceback. ASCII-safe throughout (JSON is ensure_ascii; --human is transcoded).

Usage:
  py page_fetch.py --url https://example.com/
  py page_fetch.py --url https://example.com/ --head
  py page_fetch.py --url https://example.com/ --detect-spa
  py page_fetch.py --file page.html --human
"""
import argparse
import json
import os
import re
import sys
import urllib.error

# net_safety lives in the sibling scripts/workflow/ dir; bootstrap sys.path so the shared
# SSRF guard imports cleanly (C11 treats it as a local sibling module). page_fetch routes
# EVERY fetch through net_safety.safe_open -- the one per-hop-validating, IP-pinning fetch
# -- instead of duplicating a redirect loop, so the SSRF guard + redirect handling live in
# exactly one place.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "workflow"))
from net_safety import (  # noqa: E402
    safe_open, UrlValidationError, RedirectLoopError, MaxRedirectsError,
)

DEFAULT_UA = "Mozilla/5.0 (compatible; designer-pro-seo-pagefetch/1.0; +stdlib)"
# A deliberately distinct, honestly-labeled second UA for the disclosed SPA probe --
# NOT an impersonation of any real browser or search-engine crawler.
ALT_UA = "Mozilla/5.0 (compatible; designer-pro-seo-pagefetch-altUA/1.0; SPA-probe)"

DEFAULT_MAX_HOPS = 10
DEFAULT_MAX_BYTES = 2_000_000

# Response headers worth surfacing (kept small + stable for deterministic output).
HEADER_SUBSET = (
    "content-type", "content-length", "content-encoding", "server", "location",
    "cache-control", "last-modified", "etag", "x-robots-tag", "vary",
    "strict-transport-security",
)


def _visible_text(html):
    """Strip script/style/tags and collapse whitespace to approximate the text a
    user would see -- the signal that separates a real page from a JS shell."""
    text = re.sub(r"<script\b.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_spa_shell(html):
    """Pure heuristic: does this HTML look like a client-rendered SPA shell?
    Signals: a known mount node (root/app/__next/__nuxt or <app-root>), at least
    one script tag, and almost no rendered text. Returns a disclosure-friendly dict."""
    scripts = len(re.findall(r"<script\b", html, re.I))
    has_root = bool(re.search(
        r"""<(?:div|main|section)[^>]*\bid=["'](?:root|app|__next|__nuxt|___gatsby)["']""",
        html, re.I)) or "<app-root" in html.lower()
    visible = _visible_text(html)
    looks = has_root and scripts >= 1 and len(visible) < 200
    return {
        "looks_like_spa": looks,
        "has_mount_node": has_root,
        "script_tags": scripts,
        "visible_text_len": len(visible),
    }


def _subset(headers):
    return {k: headers[k] for k in HEADER_SUBSET if k in headers}


def _ua_swap_field(performed, second_status=None, second_visible_len=None):
    field = {
        "performed": performed,
        "first_ua": DEFAULT_UA,
        "second_ua": ALT_UA if performed else None,
        "disclosure": (
            "Second fetch issued with a different User-Agent (%s) to compare "
            "server-rendered output; this can bypass UA-based content negotiation."
            % ALT_UA
        ) if performed else
        "No UA-swap performed (offline/--file/--no-network or page not a SPA shell).",
    }
    if performed:
        field["second_status"] = second_status
        field["second_visible_text_len"] = second_visible_len
    return field


def _spa_block(html, final_url, allow_network, resolve, timeout, max_bytes):
    """Run the flag-gated SPA heuristic and, only when it looks like a shell AND the
    network is allowed, a single DISCLOSED second fetch with the alt UA -- routed through
    the same IP-pinning safe_open, so the probe is SSRF-guarded too. A blocked/failed
    second fetch is best-effort: it reports performed=False (disclosure either way)."""
    base = detect_spa_shell(html)
    performed = False
    second_status = second_len = None
    if base["looks_like_spa"] and allow_network and final_url:
        try:
            resp, _chain = safe_open(final_url, method="GET",
                                     headers={"User-Agent": ALT_UA},
                                     timeout=timeout, resolve=resolve)
            try:
                second_status = getattr(resp, "status", None)
                if second_status is None:
                    second_status = getattr(resp, "code", None)
                body = resp.read(max_bytes) or b""
            finally:
                try:
                    resp.close()
                except Exception:
                    pass
            performed = True
            second_len = len(_visible_text(body.decode("utf-8", "replace")))
        except (UrlValidationError, RedirectLoopError, MaxRedirectsError,
                urllib.error.URLError, OSError, TimeoutError):
            performed = False
    base["ua_swap"] = _ua_swap_field(performed, second_status, second_len)
    return base


def _result_from_file(path, head, detect_spa):
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        return 1, {"ok": False, "mode": "file", "source": path,
                   "error": "could not read file: %s" % exc}
    text = raw.decode("utf-8", "replace")
    result = {
        "ok": True, "mode": "file", "source": path, "final_url": None,
        "status": None, "content_type": "text/html", "bytes": len(raw),
        "redirects": 0, "chain": [],
    }
    if not head:
        result["body"] = text
    if detect_spa:
        # Offline file: no second network fetch -> ua_swap.performed is False.
        result["spa_detection"] = _spa_block(text, None, allow_network=False,
                                              resolve=False, timeout=0,
                                              max_bytes=0)
    return 0, result


def _result_from_url(url, head, detect_spa, max_hops, timeout, max_bytes):
    """Fetch `url` via net_safety.safe_open -- the one centralized per-hop-validating,
    IP-pinning fetch -- then shape the JSON contract from its returned response + validated
    hop chain. No redirect/loop/SSRF logic is duplicated here; loop + hop-cap + per-hop
    blocks all surface as safe_open exceptions (each carrying a `.chain` of hops so far)."""
    method = "HEAD" if head else "GET"
    try:
        resp, chain = safe_open(url, method=method, headers={"User-Agent": DEFAULT_UA},
                                max_hops=max_hops, timeout=timeout, resolve=True)
    except UrlValidationError as exc:
        return 1, {"ok": False, "mode": "url", "source": url,
                   "error": "blocked by SSRF guard: %s" % exc,
                   "chain": getattr(exc, "chain", [])}
    except RedirectLoopError as exc:
        return 1, {"ok": False, "mode": "url", "source": url,
                   "error": "redirect loop detected", "chain": getattr(exc, "chain", [])}
    except MaxRedirectsError as exc:
        return 1, {"ok": False, "mode": "url", "source": url,
                   "error": "redirect chain exceeded max-hops (%d)" % max_hops,
                   "chain": getattr(exc, "chain", [])}
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return 1, {"ok": False, "mode": "url", "source": url,
                   "error": "fetch failed: %s" % exc, "chain": []}

    try:
        status = getattr(resp, "status", None)
        if status is None:
            status = getattr(resp, "code", None)
        headers = {k.lower(): v for k, v in resp.headers.items()}
        body = b"" if head else resp.read(max_bytes)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return 1, {"ok": False, "mode": "url", "source": url,
                   "error": "fetch failed: %s" % exc, "chain": chain}
    finally:
        try:
            resp.close()
        except Exception:
            pass

    final_url = chain[-1]["url"] if chain else url
    result = {
        "ok": True, "mode": "url", "source": url, "final_url": final_url,
        "status": status,
        "content_type": headers.get("content-type"),
        "headers": _subset(headers),
        "bytes": len(body),
        "redirects": max(0, len(chain) - 1),
        "chain": chain,
    }
    if not head:
        result["body"] = body.decode("utf-8", "replace")
    if detect_spa and not head:
        text = body.decode("utf-8", "replace")
        result["spa_detection"] = _spa_block(text, final_url, allow_network=True,
                                              resolve=True, timeout=timeout,
                                              max_bytes=max_bytes)
    return 0, result


def build_result(args):
    """Return (exit_code, result_dict) for the parsed args. No printing here."""
    if args.file:
        return _result_from_file(args.file, args.head, args.detect_spa)
    if not args.url:
        return 1, {"ok": False, "error": "no input: pass --url URL or --file PATH"}
    if args.no_network:
        return 1, {"ok": False, "mode": "url", "source": args.url,
                   "error": "network forbidden (--no-network) and no --file given"}
    return _result_from_url(args.url, args.head, args.detect_spa,
                            args.max_hops, args.timeout, args.max_bytes)


def _format_human(result):
    lines = []
    if result.get("ok"):
        lines.append("PAGE FETCH: OK")
        lines.append("  source     : %s" % result.get("source"))
        if result.get("final_url"):
            lines.append("  final url  : %s" % result.get("final_url"))
        lines.append("  status     : %s" % result.get("status"))
        lines.append("  content    : %s" % result.get("content_type"))
        lines.append("  bytes      : %s" % result.get("bytes"))
        lines.append("  redirects  : %s" % result.get("redirects"))
        for hop in result.get("chain", []):
            if hop.get("loop"):
                lines.append("    -> LOOP back to %s" % hop.get("url"))
            else:
                loc = (" -> %s" % hop["location"]) if hop.get("location") else ""
                lines.append("    [%s] %s%s" % (hop.get("status"), hop.get("url"), loc))
        spa = result.get("spa_detection")
        if spa:
            lines.append("  spa-shell  : %s (text=%s chars, scripts=%s)"
                         % (spa.get("looks_like_spa"), spa.get("visible_text_len"),
                            spa.get("script_tags")))
            ua = spa.get("ua_swap", {})
            lines.append("  ua-swap    : %s -- %s"
                         % (ua.get("performed"), ua.get("disclosure")))
    else:
        lines.append("PAGE FETCH: ERROR")
        lines.append("  source: %s" % result.get("source", result.get("mode", "?")))
        lines.append("  error : %s" % result.get("error"))
        for hop in result.get("chain", []):
            tag = "LOOP " if hop.get("loop") else ""
            lines.append("    %s[%s] %s" % (tag, hop.get("status"), hop.get("url")))
    text = "\n".join(lines)
    return text.encode("ascii", "replace").decode("ascii")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="SSRF-guarded single-URL fetcher (redirect chain + loop "
                    "detection + flag-gated SPA-shell detection).")
    ap.add_argument("--url", help="the URL to fetch (http/https)")
    ap.add_argument("--file", help="read a local HTML file instead (offline)")
    ap.add_argument("--head", action="store_true",
                    help="HEAD mode: status + headers only, no body")
    ap.add_argument("--detect-spa", action="store_true",
                    help="flag-gated SPA-shell heuristic; may issue a DISCLOSED "
                         "second fetch with a different User-Agent")
    ap.add_argument("--no-network", action="store_true",
                    help="forbid any network fetch")
    ap.add_argument("--max-hops", type=int, default=DEFAULT_MAX_HOPS,
                    help="max redirects to follow (default %d)" % DEFAULT_MAX_HOPS)
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES,
                    help="max body bytes to read (default %d)" % DEFAULT_MAX_BYTES)
    ap.add_argument("--timeout", type=float, default=10.0,
                    help="per-request timeout seconds (default 10)")
    ap.add_argument("--json", action="store_true", help="force JSON (the default)")
    ap.add_argument("--human", action="store_true",
                    help="ASCII summary instead of JSON")
    args = ap.parse_args(argv)

    code, result = build_result(args)
    if args.human and not args.json:
        print(_format_human(result))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
