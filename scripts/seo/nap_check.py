#!/usr/bin/env python3
"""
nap_check.py -- NAP (Name / Address / Phone) consistency checker across supplied
business listings (seo-local-unified flagship, Wave 3a).

Inconsistent NAP is the silent local-ranking killer: when a review-directory citation
says one phone number and the website says another, the search engine's confidence in the entity
drops and the map-pack ranking suffers. This script takes the listings the caller
supplies (`--listings FILE`), NORMALIZES each Name/Address/Phone so that cosmetic
formatting differences ("St" vs "Street", "(801) 555-0199" vs "801.555.0199") are NOT
flagged, DIFFS every listing against a canonical one, and reports the real mismatches
with a severity and a concrete fix target.

Normalization (authored from first principles; see references/seo-local-unified/nap-normalization.md):
  * phone   -> digits only; an 11-digit number with a leading US "1" drops it, so
               "+1 801 555 0199" == "(801) 555-0199".
  * address -> lowercased, punctuation stripped, "&"->"and", and a fixed
               street-type / directional / unit abbreviation map applied token-wise
               ("st"->"street", "ste"/"#"->"suite", "n"->"north", ...).
  * name    -> lowercased, "&"->"and", punctuation stripped, whitespace collapsed.
A field is "consistent" when every listing's NORMALIZED value equals the canonical's.

Severity: a divergent phone or address is HIGH (it splits leads / weakens the entity
signal); a divergent name is MEDIUM. Formatting-only differences are not findings.

Canonical selection: `--canonical SOURCE`, else the listing flagged `"primary": true`,
else the first listing.

SSRF: NAP checking is offline by default. `--verify-urls` optionally fetches each
listing's `url` to confirm the normalized phone/name actually appears on the page --
and that fetch routes through the one shared guard (`net_safety.safe_open`), never
urlopen directly. `--no-network` (or omitting `--verify-urls`) touches no network.

Output: JSON to stdout by default; `--human` prints an ASCII summary. Bad input
(missing/unreadable/unparseable file, empty list, a listing with no NAP fields) prints
a JSON error object and exits non-zero -- never a raw traceback. ASCII-safe
throughout. Standard library only; deterministic.

Usage:
  py nap_check.py --listings listings.json
  py nap_check.py --listings listings.json --canonical website --human
  py nap_check.py --listings listings.json --verify-urls
"""
import argparse
import json
import os
import re
import sys

# net_safety lives in the sibling scripts/workflow/ dir; bootstrap sys.path so the one
# shared SSRF guard imports cleanly. The optional --verify-urls fetch routes through
# safe_open -- never urllib.urlopen directly.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "workflow"))
from net_safety import (  # noqa: E402
    safe_open, UrlValidationError, RedirectLoopError, MaxRedirectsError,
)
import urllib.error  # noqa: E402

VERIFY_UA = "Mozilla/5.0 (compatible; designer-pro-seo-napcheck/1.0; +stdlib)"

# Token-wise normalization map for addresses: street types, directionals, and unit
# designators collapse to one canonical spelling so "123 Main St Ste 200" and
# "123 Main Street Suite 200" compare equal. Authored from first principles (USPS-style
# common abbreviations); no third-party source opened.
ADDRESS_TOKENS = {
    # street types
    "st": "street", "str": "street", "ave": "avenue", "av": "avenue",
    "blvd": "boulevard", "rd": "road", "dr": "drive", "ln": "lane",
    "ct": "court", "pl": "place", "sq": "square", "ter": "terrace",
    "hwy": "highway", "pkwy": "parkway", "cir": "circle", "trl": "trail",
    "rte": "route", "expy": "expressway",
    # directionals
    "n": "north", "s": "south", "e": "east", "w": "west",
    "ne": "northeast", "nw": "northwest", "se": "southeast", "sw": "southwest",
    # unit designators
    "ste": "suite", "apt": "apartment", "bldg": "building", "fl": "floor",
    "rm": "room", "dept": "department", "unit": "unit", "no": "number",
}

FIELDS = ("name", "address", "phone")
SEVERITY = {"phone": "HIGH", "address": "HIGH", "name": "MEDIUM"}
SEVERITY_REASON = {
    "phone": "different phone number splits leads and weakens the entity signal",
    "address": "different address weakens the NAP entity signal Google relies on",
    "name": "different business name reduces citation match confidence",
}


class InputError(Exception):
    """Bad caller input -> a JSON error object + non-zero exit (never a traceback)."""


class _JsonArgParser(argparse.ArgumentParser):
    """argparse's own failures (a missing required arg, a bad type/choice) must honor the
    JSON-error contract too: emit {"error": ...} to stdout + a non-zero exit, never a bare
    usage dump to stderr. stdlib + ASCII."""
    def error(self, message):
        msg = str(message).encode("ascii", "replace").decode("ascii")
        print(json.dumps({"error": msg}))
        sys.exit(2)


def norm_phone(value):
    """Digits only; drop a leading US country code so 11-digit '1NNNNNNNNNN' matches the
    10-digit form. Returns '' for an empty/None value."""
    if value is None:
        return ""
    digits = re.sub(r"\D+", "", str(value))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def norm_name(value):
    if value is None:
        return ""
    text = str(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_address(value):
    """Lowercase, strip punctuation, expand the abbreviation map token-wise, collapse
    whitespace. '#' is treated as the 'suite' designator so '#200' == 'Suite 200'."""
    if value is None:
        return ""
    text = str(value).lower().replace("&", " and ")
    text = text.replace("#", " suite ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [ADDRESS_TOKENS.get(tok, tok) for tok in text.split()]
    return re.sub(r"\s+", " ", " ".join(tokens)).strip()


NORMALIZERS = {"name": norm_name, "address": norm_address, "phone": norm_phone}


def _parse_listings(data):
    """Accept {listings:[...]} or a bare list; validate each entry. Returns
    (business_label, [listing dicts])."""
    business = None
    if isinstance(data, dict):
        business = data.get("business")
        listings = data.get("listings")
    elif isinstance(data, list):
        listings = data
    else:
        raise InputError("input must be a JSON object with 'listings' or a list")
    if not isinstance(listings, list) or not listings:
        raise InputError("no listings to check (expected a non-empty 'listings' list)")
    cleaned = []
    for idx, item in enumerate(listings):
        if not isinstance(item, dict):
            raise InputError("listing %d is not an object" % idx)
        if not any(item.get(f) for f in FIELDS):
            raise InputError(
                "listing %d (source=%r) has no name/address/phone to check"
                % (idx, item.get("source")))
        cleaned.append(item)
    return business, cleaned


def _pick_canonical(listings, canonical_source):
    """Select the canonical listing: --canonical match (case-insensitive), else the
    primary-flagged listing, else the first."""
    if canonical_source:
        want = canonical_source.strip().lower()
        for i, l in enumerate(listings):
            if str(l.get("source", "")).strip().lower() == want:
                return i
        raise InputError("no listing has source=%r for --canonical" % canonical_source)
    for i, l in enumerate(listings):
        if l.get("primary") is True:
            return i
    return 0


def _normalized(listing):
    return {f: NORMALIZERS[f](listing.get(f)) for f in FIELDS}


def _verify_url(listing, norm, *, resolve=True, timeout=10.0):
    """Optional: fetch the listing's url through the shared SSRF guard and report whether
    its normalized phone digits / name appear in the page text. Best-effort: any failure
    is reported, never raised."""
    url = listing.get("url")
    if not url:
        return {"url": None, "checked": False, "note": "no url on listing"}
    try:
        resp, _chain = safe_open(url, headers={"User-Agent": VERIFY_UA},
                                 timeout=timeout, resolve=resolve)
        try:
            body = (resp.read(2_000_000) or b"").decode("utf-8", "replace")
        finally:
            try:
                resp.close()
            except Exception:
                pass
    except (UrlValidationError, RedirectLoopError, MaxRedirectsError,
            urllib.error.URLError, OSError, TimeoutError) as exc:
        return {"url": url, "checked": False, "note": "fetch failed: %s" % exc}
    page_digits = re.sub(r"\D+", "", body)
    phone_present = bool(norm["phone"]) and norm["phone"] in page_digits
    name_present = bool(norm["name"]) and norm["name"] in norm_name(body)
    return {"url": url, "checked": True,
            "phone_on_page": phone_present, "name_on_page": name_present}


def analyze(business, listings, *, canonical_source=None, verify=False,
            resolve=True, timeout=10.0):
    """Build the full NAP consistency result. Deterministic; preserves listing order."""
    c_idx = _pick_canonical(listings, canonical_source)
    canonical = listings[c_idx]
    c_norm = _normalized(canonical)

    norms = [_normalized(l) for l in listings]

    findings = []
    matrix = []
    field_variants = {f: [] for f in FIELDS}
    for i, (listing, n) in enumerate(zip(listings, norms)):
        row = {"source": listing.get("source"), "is_canonical": i == c_idx}
        for f in FIELDS:
            if n[f] and n[f] not in field_variants[f]:
                field_variants[f].append(n[f])
            match = n[f] == c_norm[f]
            row[f + "_match"] = match
            if i != c_idx and not match:
                findings.append({
                    "source": listing.get("source"),
                    "field": f,
                    "severity": SEVERITY[f],
                    "canonical_normalized": c_norm[f],
                    "found_normalized": n[f],
                    "canonical_raw": canonical.get(f),
                    "found_raw": listing.get(f),
                    "reason": SEVERITY_REASON[f],
                })
        matrix.append(row)

    fields = {}
    for f in FIELDS:
        consistent = all(n[f] == c_norm[f] for n in norms)
        fields[f] = {"consistent": consistent,
                     "variants": sorted(field_variants[f])}

    # HIGH severity sorts before MEDIUM, then by source, for a stable, useful order.
    sev_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    findings.sort(key=lambda x: (sev_order.get(x["severity"], 9),
                                 str(x["source"]), x["field"]))

    result = {
        "ok": True,
        "business": business,
        "canonical": {
            "source": canonical.get("source"),
            "name": canonical.get("name"),
            "address": canonical.get("address"),
            "phone": canonical.get("phone"),
        },
        "listings_checked": len(listings),
        "consistent": all(fields[f]["consistent"] for f in FIELDS),
        "fields": fields,
        "findings": findings,
        "matrix": matrix,
    }
    if verify:
        result["verification"] = [
            _verify_url(l, norms[i], resolve=resolve, timeout=timeout)
            for i, l in enumerate(listings)
        ]
    return result


def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise InputError("could not read listings file: %s" % exc)
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise InputError("listings file is not valid JSON: %s" % exc)


def build_result(args):
    """Return (exit_code, result_dict). No printing here."""
    try:
        if not args.listings:
            raise InputError("no input: pass --listings FILE")
        data = _load(args.listings)
        business, listings = _parse_listings(data)
        verify = bool(args.verify_urls) and not args.no_network
        result = analyze(business, listings,
                         canonical_source=args.canonical, verify=verify,
                         resolve=True, timeout=args.timeout)
        if args.verify_urls and args.no_network:
            result["verification_note"] = "skipped URL verification (--no-network)"
        return 0, result
    except InputError as exc:
        return 2, {"ok": False, "error": str(exc)}


def _format_human(r):
    lines = []
    if not r.get("ok"):
        lines.append("NAP CHECK: ERROR")
        lines.append("  error: %s" % r.get("error"))
        return "\n".join(lines).encode("ascii", "replace").decode("ascii")
    verdict = "CONSISTENT" if r["consistent"] else "INCONSISTENT"
    lines.append("NAP CHECK: %s (%d listings)" % (verdict, r["listings_checked"]))
    c = r["canonical"]
    lines.append("  canonical (%s):" % c.get("source"))
    lines.append("    name : %s" % c.get("name"))
    lines.append("    addr : %s" % c.get("address"))
    lines.append("    phone: %s" % c.get("phone"))
    if r["findings"]:
        lines.append("  findings:")
        for f in r["findings"]:
            lines.append("    [%s] %s %s: %r != canonical %r"
                         % (f["severity"], f["source"], f["field"],
                            f["found_raw"], f["canonical_raw"]))
    else:
        lines.append("  findings: none -- all NAP fields agree after normalization")
    for fld in FIELDS:
        fi = r["fields"][fld]
        if not fi["consistent"]:
            lines.append("  %-7s variants: %s" % (fld, " | ".join(fi["variants"])))
    for v in r.get("verification", []):
        if v.get("checked"):
            lines.append("  verify %s: phone_on_page=%s name_on_page=%s"
                         % (v["url"], v.get("phone_on_page"), v.get("name_on_page")))
        elif v.get("url"):
            lines.append("  verify %s: %s" % (v["url"], v.get("note")))
    if r.get("verification_note"):
        lines.append("  note: %s" % r["verification_note"])
    return "\n".join(lines).encode("ascii", "replace").decode("ascii")


def main(argv=None):
    ap = _JsonArgParser(
        description="NAP (name/address/phone) consistency checker across listings.")
    ap.add_argument("--listings", help="JSON file: {business?, listings:[...]} or a list")
    ap.add_argument("--canonical", help="source label to treat as canonical "
                                        "(else primary:true, else the first listing)")
    ap.add_argument("--verify-urls", action="store_true",
                    help="fetch each listing's url (via the shared SSRF guard) and check "
                         "the normalized phone/name appears on the page")
    ap.add_argument("--no-network", action="store_true",
                    help="forbid any network fetch (skips --verify-urls)")
    ap.add_argument("--timeout", type=float, default=10.0,
                    help="per-request timeout seconds for --verify-urls (default 10)")
    ap.add_argument("--json", action="store_true", help="force JSON (the default)")
    ap.add_argument("--human", action="store_true", help="ASCII summary instead of JSON")
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
