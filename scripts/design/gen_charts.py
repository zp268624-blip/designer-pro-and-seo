#!/usr/bin/env python3
"""
gen_charts.py -- Clean-room chart-type recommender for the design engine.

Given a description of the DATA SHAPE (plus how many series / points it carries),
recommends a chart type from `data/chart-types.csv` with an accessibility-graded
rationale and an a11y fallback. Optionally grades a set of SERIES COLORS for WCAG
distinguishability, REUSING `gen_palettes.py`'s luminance/contrast math (the same
formula the palette generator and `render_page.py` rely on) -- no second copy.

Design notes (why this exists):
  * chart choice is a DATA-SHAPE decision, not a taste decision: the same shape maps
    to the same chart every time (deterministic), and a volume that overflows a
    shape's readable band is DISCLOSED, never silently mis-charted.
  * accessibility is first-class: every row carries an A/B/C grade (A = reads without
    color, table-friendly; B = needs labels/ordering care; C = needs a strong non-
    visual fallback) and a concrete `a11y_fallback`.

Contract (see references/ENGINE-CONTRACTS.md):
  * stdout is JSON by default; --human prints an ASCII summary.
  * deterministic: same inputs -> same output. Standard library only (+ the local
    sibling `gen_palettes` for the shared WCAG contrast math).
  * bad input (unknown shape, unreadable CSV, or an argparse failure) -> a JSON
    {"error": ...} object on stdout and a non-zero exit. `-h` exits 0.
  * offline: never fetches anything.

Usage:
  python3 gen_charts.py --shape time-series-single --series 1
  python3 gen_charts.py --shape category-compare-many --series 1 --points 30 --human
  python3 gen_charts.py --shape two-var-correlation --colors "#1f77b4,#ff7f0e" --bg "#ffffff"
  echo '{"shape":"funnel","series":1}' | python3 gen_charts.py --spec -
"""
import argparse
import csv
import json
import os
import re
import sys

import gen_palettes  # local sibling: reuse its WCAG relative-luminance + contrast math

# WCAG 1.4.11 non-text contrast: a graphical object (a series mark vs its background,
# and any two series vs each other) is distinguishable at >= 3:1. Our own grading uses it
# as the pass line over the FULL pairwise series set; the numbers come straight from
# gen_palettes.contrast_ratio.
NONTEXT_CONTRAST = 3.0
GRADE_ORDER = {"A": 0, "B": 1, "C": 2}


class ChartError(Exception):
    """Raised on bad input (unknown shape, unreadable data). Caught in main() and
    rendered as a JSON error + non-zero exit."""


class _JsonArgumentParser(argparse.ArgumentParser):
    """An ArgumentParser whose error path honors the script contract: a parse failure
    emits a JSON {"error": ...} object on stdout and exits non-zero (instead of the
    default stderr usage text). `-h`/`--help` still exits 0 via the built-in action."""

    def error(self, message):
        print(json.dumps({"error": "bad arguments: %s" % message}))
        self.exit(2)


def _data_dir(override=None):
    if override:
        return override
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "data"))


def load_chart_types(data_dir):
    """Load data/chart-types.csv into a list of dict rows (BOM/cp1252 tolerant).
    Raises ChartError if the file is missing or unreadable."""
    path = os.path.join(data_dir, "chart-types.csv")
    if not os.path.exists(path):
        raise ChartError("chart-types.csv not found in %s" % data_dir)
    for enc in ("utf-8-sig", "cp1252"):
        try:
            with open(path, newline="", encoding=enc) as f:
                rows = list(csv.DictReader(f))
            if not rows:
                raise ChartError("chart-types.csv has no rows")
            return rows
        except UnicodeDecodeError:
            continue
        except OSError as e:
            raise ChartError("could not read chart-types.csv: %s" % e)
    raise ChartError("chart-types.csv is not decodable as utf-8 or cp1252")


def _tokens(s):
    return set(t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t)


def _int(row, key, default):
    try:
        return int(str(row.get(key, "")).strip())
    except (TypeError, ValueError):
        return default


def _candidates(shape, rows):
    """Rows that plausibly serve `shape`. Exact data_shape match wins; else rows sharing
    the most shape tokens (deterministic: CSV order breaks ties). Empty -> ChartError."""
    want = (shape or "").strip().lower()
    if not want:
        raise ChartError("a data --shape (or spec 'shape') is required")
    exact = [r for r in rows if r.get("data_shape", "").strip().lower() == want]
    if exact:
        return exact, True
    qt = _tokens(want)
    # Fuzzy fallback: match a row only when the query shares the row's FAMILY token (the
    # leading slug segment, e.g. "time" for time-series-*) OR overlaps by >= 2 tokens.
    # A lone generic token ("shape", "single") must NOT match -- that grouped unrelated
    # rows. Exact-slug use (the norm) never reaches here.
    scored = []
    for i, r in enumerate(rows):
        rtoks = _tokens(r.get("data_shape"))
        family = (r.get("data_shape", "").strip().lower().split("-") or [""])[0]
        overlap = len(qt & rtoks)
        if (family and family in qt) or overlap >= 2:
            scored.append((overlap, i, r))
    if not scored:
        shapes = sorted(r.get("data_shape", "") for r in rows)
        raise ChartError("unknown data shape %r; known shapes: %s" % (shape, ", ".join(shapes)))
    best = max(s[0] for s in scored)
    near = [r for (o, i, r) in sorted(scored, key=lambda t: t[1]) if o == best]
    return near, False


def _fits(row, series, points):
    mn, mx = _int(row, "min_series", 1), _int(row, "max_series", 1)
    mp = _int(row, "max_points", 10 ** 9)
    ok_series = mn <= series <= mx
    ok_points = points is None or points <= mp
    return ok_series and ok_points


def recommend(shape, series, points, rows):
    """Recommend a chart for `shape` at the given volume. Returns a JSON-able dict.

    Selection is deterministic: prefer an exact-shape row, then a row whose volume band
    FITS (series in [min,max] and points <= max_points), then the better a11y grade,
    then CSV order. If nothing fits the volume, the closest row is still returned but a
    `volume_warning` is attached (never silently mis-charted) pointing at the fallback.
    """
    if series < 1:
        raise ChartError("--series must be >= 1")
    if points is not None and points < 0:
        raise ChartError("--points must be >= 0")
    cands, exact = _candidates(shape, rows)

    def sort_key(t):
        i, r = t
        return (0 if _fits(r, series, points) else 1,
                GRADE_ORDER.get(r.get("a11y_grade", "C"), 2), i)

    ordered = sorted(enumerate(cands), key=sort_key)
    idx, best = ordered[0]
    fits = _fits(best, series, points)

    warning = None
    if not fits:
        mn, mx = _int(best, "min_series", 1), _int(best, "max_series", 1)
        mp = _int(best, "max_points", 10 ** 9)
        reasons = []
        if not (mn <= series <= mx):
            reasons.append("%d series is outside this chart's readable band (%d-%d)"
                           % (series, mn, mx))
        if points is not None and points > mp:
            reasons.append("%d points exceeds the ~%d it stays legible for" % (points, mp))
        warning = ("volume overflow: " + "; ".join(reasons)
                   + " -- fall back to %s (%s)" % (best.get("chart_type"),
                                                   best.get("a11y_fallback")))

    def _view(r):
        return {
            "data_shape": r.get("data_shape"),
            "chart_type": r.get("chart_type"),
            "best_for": r.get("best_for"),
            "a11y_grade": r.get("a11y_grade"),
            "a11y_fallback": r.get("a11y_fallback"),
            "notes": r.get("notes"),
            "min_series": _int(r, "min_series", 1),
            "max_series": _int(r, "max_series", 1),
            "max_points": _int(r, "max_points", 0),
        }

    alternatives = [{"chart_type": r.get("chart_type"),
                     "a11y_grade": r.get("a11y_grade"),
                     "fits_volume": _fits(r, series, points)}
                    for j, r in enumerate(cands) if j != idx]

    return {
        "input": {"shape": shape, "series": series, "points": points},
        "matched_shape_exactly": exact,
        "recommended": _view(best),
        "fits_volume": fits,
        "volume_warning": warning,
        "alternatives": alternatives,
        "rationale": _rationale(best, series, points, fits),
    }


def _rationale(row, series, points, fits):
    chart, shape = row.get("chart_type"), row.get("data_shape")
    grade = row.get("a11y_grade")
    part = "%s for %s: %s." % (chart, shape, row.get("best_for"))
    part += " a11y grade %s (fallback: %s)." % (grade, row.get("a11y_fallback"))
    if not fits:
        part += " NOTE: the supplied volume is out of this chart's readable band -- see volume_warning."
    return part


def series_color_a11y(colors, bg):
    """Grade a set of series colors for WCAG distinguishability, REUSING
    gen_palettes.contrast_ratio (the shared luminance math). Returns a JSON-able report:
    each color's contrast vs the background, EVERY pair of series colors' mutual contrast
    (the full pairwise set, with an `adjacent` flag), an overall A/B/C grade, and a `needs`
    list of concrete fixes.

    Grade: A = every series clears 3:1 vs background AND every pair of series -- ADJACENT
    OR NOT -- clears 3:1 (two near-identical series confuse a reader no matter where they
    sit in the order, so the grade reflects the WORST pair ANYWHERE in the set); B = all
    clear the background but some pair is confusable; C = at least one series fails the
    background contrast. `adjacent_pairs` is kept as an extra reported detail (a subset of
    the full pairwise set). Deterministic: pairs are enumerated in (i<j) index order.
    """
    if not colors:
        raise ChartError("--colors is empty")
    try:
        per = [{"color": c, "bg_contrast": gen_palettes.contrast_ratio(c, bg)} for c in colors]
    except (ValueError, IndexError):
        raise ChartError("--colors/--bg must be #rrggbb hex values")

    needs = []
    bg_all_pass = True
    for p in per:
        p["bg_pass"] = p["bg_contrast"] >= NONTEXT_CONTRAST
        if not p["bg_pass"]:
            bg_all_pass = False
            needs.append("%s has only %.2f:1 vs the background (needs >= %.1f:1)"
                         % (p["color"], p["bg_contrast"], NONTEXT_CONTRAST))

    # Grade the FULL pairwise color set (every unordered pair, not just neighbours): a
    # duplicate/near-identical pair anywhere -- even non-adjacent -- must downgrade.
    pairs = []
    pairs_all_pass = True
    n = len(colors)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = colors[i], colors[j]
            ratio = gen_palettes.contrast_ratio(a, b)
            ok = ratio >= NONTEXT_CONTRAST
            pairs.append({"a": a, "b": b, "contrast": ratio,
                          "distinct": ok, "adjacent": (j == i + 1)})
            if not ok:
                pairs_all_pass = False
                needs.append("%s and %s are only %.2f:1 apart -- add a pattern/label or repick"
                             % (a, b, ratio))
    adjacent_pairs = [p for p in pairs if p["adjacent"]]

    if not bg_all_pass:
        grade = "C"
    elif not pairs_all_pass:
        grade = "B"
    else:
        grade = "A"
    return {"background": bg, "colors": per, "pairs": pairs,
            "adjacent_pairs": adjacent_pairs,
            "bg_all_pass": bg_all_pass, "pairs_all_pass": pairs_all_pass,
            "grade": grade, "needs": needs}


def _to_human(d):
    r = d["recommended"]
    out = ["=" * 60,
           "CHART RECOMMENDATION  --  shape: %s" % d["input"]["shape"],
           "=" * 60,
           "Chart:      %s" % r["chart_type"],
           "Best for:   %s" % r["best_for"],
           "Volume:     %d series / %s points  (band: %d-%d series, <= %d points)"
           % (d["input"]["series"],
              "?" if d["input"]["points"] is None else d["input"]["points"],
              r["min_series"], r["max_series"], r["max_points"]),
           "A11y:       grade %s  |  fallback: %s" % (r["a11y_grade"], r["a11y_fallback"]),
           "Notes:      %s" % r["notes"]]
    if d.get("volume_warning"):
        out.append("! WARNING:  %s" % d["volume_warning"])
    if d.get("alternatives"):
        alts = ", ".join("%s (%s%s)" % (a["chart_type"], a["a11y_grade"],
                                        "" if a["fits_volume"] else ", off-band")
                         for a in d["alternatives"])
        out.append("Also:       %s" % alts)
    sca = d.get("series_color_a11y")
    if sca:
        out.append("")
        out.append("Series colors: grade %s (bg pass: %s, pairs pass: %s)"
                   % (sca["grade"], sca["bg_all_pass"], sca["pairs_all_pass"]))
        for n in sca["needs"]:
            out.append("  ! %s" % n)
    return "\n".join(out)


def _load_spec(path):
    try:
        raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
        return json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        raise ChartError("could not read --spec: %s" % e)


def main(argv=None):
    ap = _JsonArgumentParser(description="Recommend a chart type from a data shape.")
    ap.add_argument("--shape", default=None, help="the data shape slug (see chart-types.csv)")
    ap.add_argument("--series", type=int, default=None, help="number of data series (default 1)")
    ap.add_argument("--points", type=int, default=None, help="number of data points/categories")
    ap.add_argument("--spec", default=None,
                    help="JSON spec file ('-' for stdin) with shape/series/points/colors/bg")
    ap.add_argument("--colors", default=None, help="comma-separated series colors (#rrggbb)")
    ap.add_argument("--bg", default="#ffffff", help="chart background color (#rrggbb)")
    ap.add_argument("--data-dir", default=None, help="override path to the data/ dir")
    ap.add_argument("--human", action="store_true", help="print an ASCII summary instead of JSON")
    args = ap.parse_args(argv)

    try:
        spec = _load_spec(args.spec) if args.spec else {}
        if not isinstance(spec, dict):
            raise ChartError("--spec must be a JSON object")
        shape = args.shape if args.shape is not None else spec.get("shape")
        series = args.series if args.series is not None else spec.get("series", 1)
        points = args.points if args.points is not None else spec.get("points")
        colors = (args.colors.split(",") if args.colors else spec.get("colors")) or None
        colors = [c.strip() for c in colors] if colors else None
        bg = args.bg if args.bg else spec.get("bg", "#ffffff")

        rows = load_chart_types(_data_dir(args.data_dir))
        result = recommend(shape, int(series), None if points is None else int(points), rows)
        if colors:
            result["series_color_a11y"] = series_color_a11y(colors, bg)
    except ChartError as e:
        print(json.dumps({"error": str(e)}))
        return 1
    except (TypeError, ValueError) as e:
        print(json.dumps({"error": "bad input: %s" % e}))
        return 1

    print(_to_human(result) if args.human else json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
