#!/usr/bin/env python3
"""
design_system.py — CSV-backed design-system reasoning engine.

Given a product type, industry, and free-text style keywords, composes a complete
design system (pattern, style, palette, typography, effects, anti-patterns,
pre-delivery checklist) by scoring rows in the local data/ libraries.

Contract (see references/ENGINE-CONTRACTS.md):
  - stdout is JSON by default; --human prints an ASCII summary.
  - Tolerates missing CSVs AND weak matches: any dimension resolved with no real
    token overlap is flagged in "_fallbacks" (so an unknown input never silently
    returns an arbitrary first row as if confident).
  - Deterministic: same inputs -> same output. Standard library only.

Usage:
  python3 design_system.py --product-type saas-landing --industry saas \\
      --keywords "modern, trustworthy, minimal" [--human] [--data-dir PATH]
"""
import argparse
import csv
import json
import os
import re
import sys

import match  # local sibling: the clean-room weighted ranker (scripts/design/match.py)

# --- ranker selection ----------------------------------------------------------------
# DEFAULT = "new" (the clean-room weighted-IDF ranker in match.py). "legacy" reproduces
# the original raw token-overlap behavior EXACTLY and is the documented one-release
# revert path (flip DPS_RANKER=legacy or pass --ranker legacy). Resolution order:
# explicit --ranker arg > DPS_RANKER env var > "new".
RANKERS = ("new", "legacy")


def _resolve_ranker(arg_value):
    if arg_value in RANKERS:
        return arg_value
    env = (os.environ.get("DPS_RANKER") or "").strip().lower()
    return env if env in RANKERS else "new"


# Per-picker field-weight ladders for the NEW ranker (our own; identity/name fields
# weigh most, mood/tags next, long prose least). See match.py for the scoring model.
PRODUCT_WEIGHTS = [("product_type", 3.0), ("industry", 2.0),
                   ("recommended_style", 1.5), ("key_sections", 1.0), ("notes", 0.8)]
STYLE_WEIGHTS = [("style", 3.0), ("mood_tags", 2.0), ("best_for", 1.5),
                 ("characteristics", 1.0), ("summary", 0.8)]
PALETTE_WEIGHTS = [("name", 2.5), ("mood", 2.0), ("industry", 2.0), ("tags", 1.2)]
TYPO_WEIGHTS = [("name", 2.5), ("mood", 2.0), ("best_for", 1.5)]

AA_BONUS = 0.5       # palette tie-break: a WCAG-AA-passing palette edges a tie (< floor)
AVOID_PENALTY = 2.0  # style: query token in a row's avoid_for damps it (legacy parity)


def _data_dir(override=None):
    if override:
        return override
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "data"))


def _load(data_dir, filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        return None
    # Tolerate a non-UTF-8 data CSV (a hand-edited cp1252 file shouldn't crash the
    # engine); if it is truly unreadable, return None so the fallback path flags it.
    for enc in ("utf-8-sig", "cp1252"):
        try:
            with open(path, newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    return None


def _tokens(s):
    return set(t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t)


def _overlap(query_tokens, *fields):
    row_tokens = set()
    for fld in fields:
        row_tokens |= _tokens(fld)
    return len(query_tokens & row_tokens)


def pick_product(rows, product_type, industry, qtokens, ranker="new"):
    """Returns (row_or_None, matched_bool). Exact product_type match always wins (both
    rankers); only the fall-through scoring differs by ranker."""
    if not rows:
        return None, False
    for r in rows:
        if r.get("product_type", "").lower() == (product_type or "").lower():
            return r, True
    pt = _tokens(product_type) | _tokens(industry) | qtokens
    if ranker == "legacy":
        best, best_s = None, 0
        for r in rows:
            s = _overlap(pt, r.get("product_type"), r.get("industry"),
                         r.get("notes"), r.get("key_sections"), r.get("recommended_style"))
            if s > best_s:
                best, best_s = r, s
        return (best, True) if best_s > 0 else (rows[0], False)
    rr = match.rank(rows, pt, PRODUCT_WEIGHTS)
    return (rr.row, rr.matched)


def pick_style(rows, want_style, qtokens, mood_tokens, ranker="new"):
    """Returns (row, matched_bool, override, ambiguous).

    `override` is (default_style, chosen_style) when the user's keywords explicitly
    name a style other than the product's recommended default; in that case the engine
    honors the stated intent and the caller records the swap in "_fallbacks", so an
    explicit style keyword is never silently discarded.

    The explicit-style-override SUBSET rule is ranker-independent (it is intent
    resolution, not scoring); only the no-default-on-file fall-through differs by ranker.
    """
    if not rows:
        return None, False, None, False
    want_lc = (want_style or "").lower()
    want_row = next((r for r in rows if r.get("style", "").lower() == want_lc), None)

    if want_row is not None:
        # A keyword set that explicitly NAMES another style on file overrides the
        # product default. "Names" means every token of that style's name appears in
        # the keywords (subset), so a lone common adjective ("clean", "dark", "soft")
        # can't hijack a multi-word style, and "brutalist" can't ambiguously match
        # "neo-brutalist". Ties prefer the most specific (longest) name, then CSV order.
        named, named_score = None, 0
        for r in rows:
            if r is want_row:
                continue
            name_tokens = _tokens(r.get("style"))
            if name_tokens and name_tokens <= qtokens and len(name_tokens) > named_score:
                named, named_score = r, len(name_tokens)
        if named is not None:
            return named, True, (want_row.get("style"), named.get("style")), False
        return want_row, True, None, False

    # No exact default row on file: score by keyword/mood overlap (closest wins).
    q = qtokens | mood_tokens | _tokens(want_style)
    if ranker == "legacy":
        best, best_s = None, 0
        for r in rows:
            s = _overlap(q, r.get("style"), r.get("mood_tags"),
                         r.get("characteristics"), r.get("best_for"), r.get("summary"))
            if q & _tokens(r.get("avoid_for")):
                s -= 2
            if s > best_s:
                best, best_s = r, s
        return (best, True, None, False) if best_s > 0 else (rows[0], False, None, False)

    def _avoid(r, score):
        return score - AVOID_PENALTY if (q & _tokens(r.get("avoid_for"))) else score
    rr = match.rank(rows, q, STYLE_WEIGHTS, adjust=_avoid)
    return (rr.row, rr.matched, None, rr.ambiguous)


def pick_palette(rows, industry, palette_mood, qtokens, ranker="new"):
    """Returns (row, matched_bool, ambiguous)."""
    if not rows:
        return None, False, False
    q = _tokens(industry) | _tokens(palette_mood) | qtokens
    if ranker == "legacy":
        best = None
        for r in rows:
            ov = _overlap(q, r.get("industry"), r.get("mood"), r.get("tags"), r.get("name"))
            score = ov + (1 if r.get("aa_body_text") == "pass" else 0)
            if best is None or score > best[1]:
                best = (r, score, ov)
        return (best[0], best[2] > 0, False)

    def _aa(r, score):
        return score + (AA_BONUS if r.get("aa_body_text") == "pass" else 0.0)
    rr = match.rank(rows, q, PALETTE_WEIGHTS, adjust=_aa)
    return (rr.row, rr.matched, rr.ambiguous)


def pick_typography(rows, typo_mood, product_type, qtokens, ranker="new"):
    """Returns (row, matched_bool, ambiguous)."""
    if not rows:
        return None, False, False
    q = _tokens(typo_mood) | _tokens(product_type) | qtokens
    if ranker == "legacy":
        best, best_s = None, 0
        for r in rows:
            s = _overlap(q, r.get("mood"), r.get("best_for"), r.get("name"))
            if s > best_s:
                best, best_s = r, s
        return (best, True, False) if best_s > 0 else (rows[0], False, False)
    rr = match.rank(rows, q, TYPO_WEIGHTS)
    return (rr.row, rr.matched, rr.ambiguous)


EFFECT_DEFAULTS = {
    "minimal": dict(radius="6px", shadow="subtle (0 1px 2px rgba(0,0,0,.06))", motion="150ms ease-out"),
    "luxury-serif": dict(radius="2px", shadow="none / hairline border", motion="400ms ease"),
    "neo-brutalist": dict(radius="0px", shadow="hard offset (4px 4px 0 #000)", motion="120ms steps"),
    "soft-ui": dict(radius="16px", shadow="soft (0 8px 24px rgba(0,0,0,.08))", motion="250ms ease-in-out"),
    "glassmorphism": dict(radius="14px", shadow="blur + glow", motion="300ms ease"),
    "dark-tech": dict(radius="8px", shadow="glow accent", motion="180ms ease-out"),
    "claymorphism": dict(radius="22px", shadow="puffy dual-tone", motion="300ms spring"),
    "_default": dict(radius="8px", shadow="medium (0 4px 12px rgba(0,0,0,.08))", motion="200ms ease-out"),
}


def compose(args):
    data_dir = _data_dir(args.data_dir)
    qtokens = _tokens(args.keywords)
    ranker = _resolve_ranker(getattr(args, "ranker", None))
    fallbacks = []

    styles = _load(data_dir, "ui-styles.csv")
    palettes = _load(data_dir, "color-palettes.csv")
    fonts = _load(data_dir, "font-pairings.csv")
    uxrules = _load(data_dir, "ux-rules.csv")
    products = _load(data_dir, "product-types.csv")

    for name, rows in [("ui-styles", styles), ("color-palettes", palettes),
                       ("font-pairings", fonts), ("ux-rules", uxrules),
                       ("product-types", products)]:
        if rows is None:
            fallbacks.append(f"{name}.csv missing — used heuristic defaults")

    prod, prod_ok = pick_product(products, args.product_type, args.industry, qtokens, ranker)
    if products and not prod_ok:
        fallbacks.append("product-type: no match for inputs — used generic landing defaults")
    want_style = prod.get("recommended_style") if prod else None
    palette_mood = prod.get("palette_mood") if prod else None
    typo_mood = prod.get("typography_mood") if prod else None
    pattern = prod.get("recommended_pattern") if prod else "hero-centric"
    key_sections = (prod.get("key_sections") if prod else "hero;value;social-proof;features;cta")
    anti_from_product = (prod.get("anti_patterns") if prod else "")

    mood_tokens = _tokens(palette_mood) | _tokens(typo_mood)
    style, style_ok, style_override, style_amb = pick_style(styles, want_style, qtokens, mood_tokens, ranker)
    palette, palette_ok, palette_amb = pick_palette(palettes, args.industry, palette_mood, qtokens, ranker)
    typo, typo_ok, typo_amb = pick_typography(fonts, typo_mood, args.product_type, qtokens, ranker)

    if styles and not style_ok:
        fallbacks.append("style: no strong match — returned closest available (refine keywords to improve)")
    elif style_override:
        fallbacks.append("style: keyword '%s' overrode the product default '%s' (drop the keyword to keep the default)"
                         % (style_override[1], style_override[0]))
    elif style_amb:
        fallbacks.append("style: top matches were close — returned the highest-ranked (refine keywords to disambiguate)")
    if palettes and not palette_ok:
        fallbacks.append("palette: no strong match — returned closest available")
    elif palette_amb:
        fallbacks.append("palette: top matches were close — returned the highest-ranked (refine keywords to disambiguate)")
    if fonts and not typo_ok:
        fallbacks.append("typography: no strong match — returned closest available")
    elif typo_amb:
        fallbacks.append("typography: top matches were close — returned the highest-ranked (refine keywords to disambiguate)")

    style_name = style.get("style") if style else (want_style or "minimal")
    effects = EFFECT_DEFAULTS.get(style_name, EFFECT_DEFAULTS["_default"])

    anti = []
    for chunk in [anti_from_product, (style.get("avoid_for") if style else "")]:
        anti += [a.strip() for a in re.split(r"[;,]", chunk or "") if a.strip()]
    anti = list(dict.fromkeys(anti))

    if uxrules:
        checklist = [r.get("rule") for r in uxrules if r.get("priority") in ("critical", "high")]
    else:
        checklist = [
            "One primary CTA per view",
            "Value proposition visible without scrolling",
            "Body text contrast >= 4.5:1",
            "Tap targets >= 44x44 px",
            "LCP < 2.5s, CLS < 0.1, INP < 200ms",
        ]

    result = {
        "input": {"product_type": args.product_type, "industry": args.industry,
                  "keywords": args.keywords},
        "pattern": pattern,
        "style": {
            "name": style_name,
            "summary": style.get("summary") if style else None,
            "characteristics": style.get("characteristics") if style else None,
            "best_for": style.get("best_for") if style else None,
        },
        "palette": ({
            "name": palette.get("name"), "primary": palette.get("primary"),
            "secondary": palette.get("secondary"), "accent": palette.get("accent"),
            "bg": palette.get("bg"), "surface": palette.get("surface"),
            "text": palette.get("text"), "success": palette.get("success"),
            "warning": palette.get("warning"), "error": palette.get("error"),
            # modern semantic slots (additive; present when the palette CSV supplies them)
            "card": palette.get("card"), "muted": palette.get("muted"),
            "border": palette.get("border"), "ring": palette.get("ring"),
            "destructive": palette.get("destructive"),
            "text_on_bg_contrast": palette.get("text_on_bg_contrast"),
            "on_primary": palette.get("on_primary"),
            "aa_body_text": palette.get("aa_body_text"),
        } if palette else None),
        "typography": ({
            "pairing": typo.get("name"), "heading_font": typo.get("heading_font"),
            "body_font": typo.get("body_font"), "heading_weight": typo.get("heading_weight"),
            "body_weight": typo.get("body_weight"), "google_fonts": typo.get("google_fonts"),
        } if typo else None),
        "effects": effects,
        "key_sections": [s.strip() for s in re.split(r"[;,]", key_sections) if s.strip()],
        "anti_patterns": anti,
        "pre_delivery_checklist": checklist,
        "_fallbacks": fallbacks,
    }
    return result


def to_human(d):
    out = ["=" * 60]
    p = d["input"]
    out.append(f"DESIGN SYSTEM  —  {p['product_type']} / {p['industry']}")
    out.append("=" * 60)
    out.append(f"Pattern:    {d['pattern']}")
    s = d["style"]
    out.append(f"Style:      {s['name']}" + (f" — {s['summary']}" if s.get('summary') else ""))
    pal = d["palette"]
    if pal:
        out.append("Palette:    " + pal["name"])
        out.append(f"  primary {pal['primary']}  secondary {pal['secondary']}  accent {pal['accent']}")
        out.append(f"  bg {pal['bg']}  surface {pal['surface']}  text {pal['text']}  (text/bg {pal['text_on_bg_contrast']}, AA {pal['aa_body_text']})")
        out.append(f"  on-primary text {pal.get('on_primary')}  |  success {pal['success']}  warning {pal['warning']}  error {pal['error']}")
        if pal.get("card"):
            out.append(f"  card {pal['card']}  muted {pal['muted']}  border {pal['border']}  ring {pal['ring']}  destructive {pal['destructive']}")
    t = d["typography"]
    if t:
        out.append("Type:       " + f"{t['pairing']} — {t['heading_font']} {t['heading_weight']} / {t['body_font']} {t['body_weight']}")
    e = d["effects"]
    out.append(f"Effects:    radius {e['radius']} | shadow {e['shadow']} | motion {e['motion']}")
    out.append("Sections:   " + ", ".join(d["key_sections"]))
    if d["anti_patterns"]:
        out.append("Avoid:      " + ", ".join(d["anti_patterns"]))
    out.append("")
    out.append("Pre-delivery checklist:")
    for c in d["pre_delivery_checklist"]:
        out.append(f"  [ ] {c}")
    if d["_fallbacks"]:
        out.append("")
        out.append("Notes (fallbacks):")
        for fb in d["_fallbacks"]:
            out.append(f"  ! {fb}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Compose a design system from local data libraries.")
    ap.add_argument("--product-type", default="", help="e.g. saas-landing, restaurant, luxury-brand")
    ap.add_argument("--industry", default="", help="e.g. saas, healthcare, ecommerce")
    ap.add_argument("--keywords", default="", help="free-text style keywords, comma separated")
    ap.add_argument("--data-dir", default=None, help="override path to data/ dir")
    ap.add_argument("--human", action="store_true", help="print ASCII summary instead of JSON")
    ap.add_argument("--ranker", choices=RANKERS, default=None,
                    help="scoring ranker: 'new' (default, weighted-IDF) or 'legacy' "
                         "(raw token-overlap revert path); also via DPS_RANKER env var")
    args = ap.parse_args()
    result = compose(args)
    print(to_human(result) if args.human else json.dumps(result, indent=2))


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    main()
