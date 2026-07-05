#!/usr/bin/env python3
"""
business_type.py -- classify a website into a business type + industry vertical
from on-page / schema / keyword SIGNALS (no network; operates on provided data).

The W4 `seo-audit` socket calls this first so it can route conditional specialists
(e.g. ecommerce -> seo-ecommerce, local -> seo-local-unified). The classifier is a
deterministic weighted-evidence model over a fixed rule table: every business type
declares which signals count as evidence for it; the script tallies the evidence
the input actually carries, picks the top type, and reports the confidence plus the
exact signals that drove the decision. It never fabricates -- an empty/uninformative
signal set returns business_type="unknown" with confidence 0.0.

Recognised types: saas, ecommerce, local, sab (service-area business), publisher,
agency. Vertical (restaurant, healthcare, legal, home-services, real-estate,
automotive, finance, education, ...) is derived from the same signals; default
"general".

Input signals (any subset; all optional) via --signals '<json>' or --file PATH:
  schema_types       : list of Schema.org @type strings found on the site
  keywords           : list of on-page / nav / CTA phrases (lowercased internally)
  page_types         : object mapping a page-type label -> count (e.g. product: 240)
  has_cart           : bool   -- a shopping cart / checkout is present
  has_pricing        : bool   -- a pricing / plans page is present
  has_subscription   : bool   -- recurring billing / plans language
  has_address        : bool   -- a physical street address / NAP block
  has_service_area   : bool   -- "areas we serve" / service-radius language
  industry           : string -- an explicit vertical hint, if the caller has one

Output: JSON to stdout by default; --human prints an ASCII summary. On bad input
(unparseable JSON, missing input, wrong shape) it prints a JSON error object and
exits non-zero -- never a raw traceback. Standard library only; deterministic.

Usage:
  py business_type.py --signals '{"schema_types":["Product"],"has_cart":true}'
  py business_type.py --file signals.json --human
"""
import argparse
import json
import sys


# Each business type declares evidence rules. A rule is (signal-test, weight,
# human-readable driver label). Weights are our own, chosen so a single strong
# structural signal (schema/cart) outweighs a single soft keyword.
def _kw(*needles):
    """Return a predicate: true if any needle is a substring of any keyword."""
    needles = tuple(n.lower() for n in needles)
    def test(sig):
        for kw in sig["_keywords"]:
            for n in needles:
                if n in kw:
                    return True
        return False
    return test


def _schema(*types):
    types = tuple(t.lower() for t in types)
    def test(sig):
        return any(t in sig["_schema"] for t in types)
    return test


def _flag(name):
    def test(sig):
        return bool(sig.get(name))
    return test


def _page(label, minimum=1):
    def test(sig):
        return sig["_pages"].get(label, 0) >= minimum
    return test


# (predicate, weight, driver-label)
TYPE_RULES = {
    "saas": [
        (_schema("softwareapplication", "webapplication"), 5, "SoftwareApplication schema"),
        (_flag("has_subscription"), 4, "subscription / recurring billing"),
        (_kw("free trial", "start free", "14-day"), 4, "free-trial CTA"),
        (_kw("sign up", "get started", "create account"), 2, "sign-up CTA"),
        (_kw("pricing", "plans"), 2, "pricing/plans language"),
        (_kw("api", "integrations", "sdk", "webhook"), 3, "API / integrations"),
        (_kw("dashboard", "workspace", "no credit card"), 2, "product-app language"),
        (_flag("has_pricing"), 1, "pricing page"),
    ],
    "ecommerce": [
        (_schema("product", "offer", "aggregateoffer"), 5, "Product/Offer schema"),
        (_flag("has_cart"), 5, "shopping cart / checkout"),
        (_kw("add to cart", "add to bag", "checkout"), 4, "cart CTA"),
        (_kw("free shipping", "shipping", "returns"), 2, "shipping/returns language"),
        (_kw("buy now", "shop now", "in stock", "sku"), 2, "purchase language"),
        (_page("product", 5), 4, "many product pages"),
        (_page("category", 1), 1, "category pages"),
    ],
    "local": [
        (_schema("localbusiness", "store", "restaurant", "dentist", "medicalbusiness"),
         5, "LocalBusiness schema"),
        (_flag("has_address"), 4, "physical address / NAP"),
        (_kw("hours", "directions", "visit us", "our location", "find us"),
         3, "storefront language"),
        (_kw("book a table", "reservations", "walk-in"), 2, "on-site service language"),
        (_page("location", 1), 2, "location page(s)"),
    ],
    "sab": [
        (_flag("has_service_area"), 5, "service-area language"),
        (_kw("areas we serve", "service area", "we come to you", "serving"),
         4, "areas-served language"),
        (_kw("free estimate", "free quote", "emergency service", "licensed and insured"),
         3, "service-pro CTA"),
        (_schema("localbusiness", "homeandconstructionbusiness", "plumber",
                 "electrician", "roofingcontractor"), 2, "service-business schema"),
    ],
    "publisher": [
        (_schema("article", "newsarticle", "blogposting", "newsmediaorganization"),
         5, "Article/News schema"),
        (_page("blog", 20), 4, "high article volume"),
        (_kw("subscribe", "newsletter", "latest news", "read more", "by "),
         2, "editorial language"),
        (_kw("advertise", "sponsored", "press"), 1, "ad-supported language"),
    ],
    "agency": [
        (_schema("professionalservice", "organization"), 2, "Organization schema"),
        (_kw("our work", "portfolio", "case studies", "case study"),
         4, "portfolio language"),
        (_kw("our services", "what we do", "our clients", "clients"),
         3, "services/clients language"),
        (_kw("get a quote", "book a call", "work with us", "let's talk"),
         2, "agency CTA"),
    ],
}

# Vertical detection: (vertical, predicate). First match in this fixed order wins,
# so the result is deterministic. Driven by keywords, schema, and the explicit hint.
VERTICAL_RULES = [
    ("restaurant", _kw("menu", "reservation", "restaurant", "dine", "cuisine", "takeout")),
    ("healthcare", _kw("patient", "appointment", "clinic", "dental", "dentist",
                        "doctor", "medical", "therapy", "treatment")),
    ("legal", _kw("attorney", "lawyer", "law firm", "legal", "litigation", "counsel")),
    ("home-services", _kw("plumbing", "hvac", "roofing", "electrician", "remodel",
                          "contractor", "landscaping", "cleaning")),
    ("real-estate", _kw("listing", "for sale", "realtor", "property", "mls", "mortgage")),
    ("automotive", _kw("dealership", "auto repair", "vehicle", "car wash", "tires",
                       "automotive")),
    ("finance", _kw("invoice", "accounting", "bookkeeping", "tax", "wealth",
                    "insurance", "loan")),
    ("education", _kw("course", "enroll", "tuition", "curriculum", "student",
                      "academy", "bootcamp")),
    ("fitness", _kw("gym", "workout", "personal trainer", "membership", "yoga")),
    ("beauty", _kw("salon", "spa", "barber", "skincare", "cosmetic")),
]


def _normalize_signals(raw):
    """Project the raw signal object into the internal shape the rules consume.
    Raises ValueError on a non-object input."""
    if not isinstance(raw, dict):
        raise ValueError("signals must be a JSON object")
    sig = dict(raw)
    kws = raw.get("keywords") or []
    if not isinstance(kws, list):
        raise ValueError("keywords must be a list")
    sig["_keywords"] = [str(k).lower() for k in kws]
    schema = raw.get("schema_types") or []
    if not isinstance(schema, list):
        raise ValueError("schema_types must be a list")
    sig["_schema"] = set(str(t).lower() for t in schema)
    pages = raw.get("page_types") or {}
    if not isinstance(pages, dict):
        raise ValueError("page_types must be an object")
    clean_pages = {}
    for k, v in pages.items():
        try:
            clean_pages[str(k).lower()] = int(v)
        except (TypeError, ValueError):
            raise ValueError("page_types values must be integers")
    sig["_pages"] = clean_pages
    return sig


def classify(raw_signals):
    """Return the classification dict for a raw signal object. Deterministic."""
    sig = _normalize_signals(raw_signals)

    scores = {}
    drivers = {}
    for btype, rules in TYPE_RULES.items():
        total = 0
        hit = []
        for predicate, weight, label in rules:
            if predicate(sig):
                total += weight
                hit.append(label)
        scores[btype] = total
        drivers[btype] = hit

    # Rank deterministically: highest score, then alphabetical type name on ties.
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top_type, top_score = ranked[0]
    total_evidence = sum(scores.values())

    if top_score == 0:
        return {
            "business_type": "unknown",
            "vertical": _detect_vertical(sig) or "general",
            "confidence": 0.0,
            "drivers": [],
            "scores": scores,
            "runner_up": None,
            "note": "no business-type signals present; not enough evidence to classify",
        }

    # Confidence: the winner's share of all collected evidence, blended with its
    # margin over the runner-up so a clear winner reads as more confident than a
    # near-tie. Bounded to [0, 1], rounded for stable output.
    share = top_score / total_evidence if total_evidence else 0.0
    runner_score = ranked[1][1] if len(ranked) > 1 else 0
    margin = (top_score - runner_score) / top_score if top_score else 0.0
    confidence = round(0.5 * share + 0.5 * margin, 3)

    return {
        "business_type": top_type,
        "vertical": _detect_vertical(sig) or "general",
        "confidence": confidence,
        "drivers": drivers[top_type],
        "scores": scores,
        "runner_up": ranked[1][0] if len(ranked) > 1 and ranked[1][1] > 0 else None,
    }


def _detect_vertical(sig):
    explicit = sig.get("industry")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().lower()
    for vertical, predicate in VERTICAL_RULES:
        if predicate(sig):
            return vertical
    return None


def _load_signals(args):
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            return json.load(fh)
    if args.signals is not None:
        return json.loads(args.signals)
    raise ValueError("provide --signals '<json>' or --file PATH")


def _format_human(result):
    lines = [
        "Business type: %s" % result["business_type"],
        "  vertical  : %s" % result["vertical"],
        "  confidence: %s" % result["confidence"],
    ]
    if result.get("runner_up"):
        lines.append("  runner-up : %s" % result["runner_up"])
    if result.get("drivers"):
        lines.append("  drivers   :")
        for d in result["drivers"]:
            lines.append("    - %s" % d)
    elif result.get("note"):
        lines.append("  note      : %s" % result["note"])
    text = "\n".join(lines)
    return text.encode("ascii", "replace").decode("ascii")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Classify a site into a business type + vertical from signals.")
    ap.add_argument("--signals", help="signal data as a JSON string")
    ap.add_argument("--file", help="path to a JSON file of signals")
    ap.add_argument("--human", action="store_true", help="ASCII summary")
    args = ap.parse_args(argv)

    try:
        raw = _load_signals(args)
    except FileNotFoundError:
        print(json.dumps({"error": "signals file not found: %s" % args.file}))
        return 1
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": "invalid JSON signals: %s" % exc}))
        return 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    try:
        result = classify(raw)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

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
