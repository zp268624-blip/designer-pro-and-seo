#!/usr/bin/env python3
"""
gen_palettes.py — Clean-room color-palette generator.

Generates `data/color-palettes.csv` programmatically from base hue families using
HSL math + WCAG contrast computation. Nothing is copied from any external palette
list; every value here is computed by this script. Re-running with the same inputs
reproduces the same file (idempotent), which is the provenance guarantee recorded
in references/PROVENANCE.md.

Usage:
    python3 gen_palettes.py            # writes ../../data/color-palettes.csv
    python3 gen_palettes.py --print    # prints CSV to stdout instead
"""
import argparse
import colorsys
import csv
import json
import os
import sys

# (industry, mood, base_hue_degrees, saturation, lightness_of_primary)
# Hues chosen across the wheel so the library spans warm/cool/neutral families.
FAMILIES = [
    ("saas",            "trustworthy-cool",   222, 0.72, 0.52),
    ("saas",            "modern-violet",      262, 0.62, 0.55),
    ("fintech",         "confident-navy",     214, 0.66, 0.40),
    ("healthcare",      "calm-teal",          184, 0.55, 0.42),
    ("wellness",        "soft-sage",          150, 0.38, 0.46),
    ("ecommerce",       "energetic-coral",     14, 0.78, 0.55),
    ("ecommerce",       "premium-plum",       300, 0.42, 0.42),
    ("luxury",          "gold-on-charcoal",    42, 0.62, 0.50),
    ("hospitality",     "warm-terracotta",     20, 0.58, 0.50),
    ("food-bev",        "appetite-red",         8, 0.74, 0.52),
    ("realestate",      "grounded-slate",     208, 0.30, 0.45),
    ("legal",           "authoritative-blue", 224, 0.50, 0.34),
    ("education",       "friendly-azure",     200, 0.70, 0.50),
    ("nonprofit",       "hopeful-green",      138, 0.55, 0.44),
    ("creative",        "bold-magenta",       324, 0.72, 0.55),
    ("creative",        "electric-cyan",      190, 0.80, 0.52),
    ("tech-hardware",   "industrial-steel",   210, 0.18, 0.44),
    ("beauty",          "blush-rose",         342, 0.55, 0.62),
    ("fitness",         "high-energy-lime",    92, 0.68, 0.48),
    ("travel",          "horizon-teal",       176, 0.62, 0.46),
    ("kids",            "playful-tangerine",   32, 0.85, 0.56),
    ("eco",             "natural-forest",     128, 0.45, 0.38),
    ("automotive",      "performance-red",      2, 0.70, 0.48),
    ("media",           "editorial-ink",      230, 0.22, 0.30),
]


def hsl_to_hex(h_deg, s, l):
    """h in degrees, s/l in 0..1 -> #rrggbb."""
    r, g, b = colorsys.hls_to_rgb((h_deg % 360) / 360.0, l, s)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(c1, c2):
    l1, l2 = relative_luminance(c1), relative_luminance(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return round((hi + 0.05) / (lo + 0.05), 2)


DARK_INK = "#111418"  # the same near-black the on-primary picker uses


def _mix(c1, c2, t):
    """Deterministic sRGB blend of two #rrggbb colors; t in 0..1 = weight toward c2.
    Integer channels + round() -> byte-reproducible, no float drift in the output."""
    a = [int(c1.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#{:02x}{:02x}{:02x}".format(
        *[round(a[k] + (b[k] - a[k]) * t) for k in range(3)])


def _contrast_floor(color, against, target, steps=20, toward=DARK_INK):
    """Deepen `color` toward `toward` in fixed integer steps only until it clears a
    contrast `target` against `against` (WCAG 1.4.11 non-text 3:1 for focus rings and
    action fills). Returns `color` untouched when it already clears; the stepped search
    is deterministic, so the result is byte-reproducible."""
    if contrast_ratio(color, against) >= target:
        return color
    for i in range(1, steps + 1):
        c = _mix(color, toward, i / steps)
        if contrast_ratio(c, against) >= target:
            return c
    return _mix(color, toward, 1.0)


def build_palette(industry, mood, hue, sat, light):
    primary = hsl_to_hex(hue, sat, light)
    # Secondary: analogous shift, slightly desaturated.
    secondary = hsl_to_hex(hue + 28, max(0.0, sat - 0.12), min(0.92, light + 0.06))
    # Accent: near-complementary for contrast pop.
    accent = hsl_to_hex(hue + 165, min(0.95, sat + 0.10), 0.55)
    # Neutral surfaces derived from a faint tint of the primary hue.
    bg = hsl_to_hex(hue, 0.16, 0.985)        # near-white tinted
    surface = hsl_to_hex(hue, 0.14, 0.955)   # card surface
    text = hsl_to_hex(hue, 0.22, 0.16)       # near-black tinted
    success = hsl_to_hex(145, 0.55, 0.40)
    warning = hsl_to_hex(38, 0.85, 0.50)
    error = hsl_to_hex(2, 0.70, 0.48)
    text_on_bg = contrast_ratio(text, bg)
    primary_on_bg = contrast_ratio(primary, bg)
    aa_body = "pass" if text_on_bg >= 4.5 else "fail"
    # Best text color to place ON the primary (e.g. button labels), chosen by contrast.
    white, dark = "#ffffff", "#111418"
    on_primary = white if contrast_ratio(white, primary) >= contrast_ratio(dark, primary) else dark
    on_primary_contrast = round(max(contrast_ratio(white, primary), contrast_ratio(dark, primary)), 2)
    # Modern semantic slots (computed from the colors above + the luminance formula;
    # additive, still byte-reproducible). card = an elevated surface (lighter than the
    # base surface); muted / border = a surface nudged toward text by a small / larger
    # amount (a recessed panel, then a visible-but-subtle divider); ring = the brand
    # primary deepened just enough to clear the WCAG 1.4.11 3:1 non-text floor for a
    # focus indicator; destructive = the error red held to the same 3:1 action floor.
    card = _mix(surface, white, 0.5)
    muted = _mix(surface, text, 0.06)
    border = _mix(surface, text, 0.16)
    ring = _contrast_floor(primary, bg, 3.0)
    destructive = _contrast_floor(error, bg, 3.0)
    name = f"{industry}-{mood}"
    tags = ";".join([industry, mood.split('-')[0], "light", "generated"])
    return {
        "name": name,
        "industry": industry,
        "mood": mood,
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "bg": bg,
        "surface": surface,
        "text": text,
        "success": success,
        "warning": warning,
        "error": error,
        "card": card,
        "muted": muted,
        "border": border,
        "ring": ring,
        "destructive": destructive,
        "text_on_bg_contrast": text_on_bg,
        "primary_on_bg_contrast": primary_on_bg,
        "on_primary": on_primary,
        "on_primary_contrast": on_primary_contrast,
        "aa_body_text": aa_body,
        "tags": tags,
        "source": "generated:gen_palettes.py",
        "license": "proprietary",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", dest="to_stdout")
    args = ap.parse_args()

    rows = [build_palette(*f) for f in FAMILIES]
    fieldnames = list(rows[0].keys())

    if args.to_stdout:
        w = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
        return

    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.normpath(os.path.join(here, "..", "..", "data", "color-palettes.csv"))
    try:
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
    except OSError as e:
        print(json.dumps({"error": "could not write %s: %s" % (out, e)}))
        sys.exit(1)
    # Contract: JSON status to stdout by default (the CSV itself is available via --print).
    print(json.dumps({"wrote": out, "palettes": len(rows)}, indent=2))


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    main()
