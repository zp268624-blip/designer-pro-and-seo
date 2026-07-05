#!/usr/bin/env python3
"""gen_ranker_baseline.py -- full-corpus snapshot harness for the design ranker.

Runs scripts/design/design_system.compose() for EVERY product_type in
data/product-types.csv across a fixed keyword matrix (the product's own moods, a
few generic sets, a lone-adjective non-hijack case, and an explicit-style-override
case), capturing the chosen pattern / style / palette / typography / fallbacks per
input. This is the moat regression anchor (MASTER-PLAN 6.1, moat-safe rollout step 1).

The matrix is defined once here and imported by tests/test_match.py so the legacy
baseline and the new-ranker snapshot are produced over identical inputs.

Usage:
  py tests/fixtures/gen_ranker_baseline.py --ranker legacy --out tests/fixtures/ranker_baseline.json
  py tests/fixtures/gen_ranker_baseline.py --ranker new    --out <tmp.json>
  py tests/fixtures/gen_ranker_baseline.py --ranker new --diff tests/fixtures/ranker_baseline.json
"""
import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts", "design"))
import design_system as ds  # noqa: E402

DATA = os.path.join(ROOT, "data")


class _Args:
    """Minimal stand-in for the argparse namespace compose() consumes."""
    def __init__(self, product_type, industry, keywords, ranker):
        self.product_type = product_type
        self.industry = industry
        self.keywords = keywords
        self.data_dir = None
        self.ranker = ranker


def _products():
    with open(os.path.join(DATA, "product-types.csv"), newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def keyword_sets(prod):
    """The fixed per-product keyword matrix (deterministic, ordered)."""
    palette_mood = (prod.get("palette_mood") or "").replace(";", ", ")
    typo_mood = (prod.get("typography_mood") or "").replace(";", ", ")
    own = ", ".join(x for x in (palette_mood, typo_mood) if x)
    return [
        ("default", ""),
        ("own-mood", own),
        ("modern-minimal", "modern, minimal"),
        ("bold-premium", "bold, premium"),
        ("lone-clean", "clean"),
        ("override-brutalist", "brutalist"),
    ]


def snapshot(ranker):
    """Run the full matrix under `ranker` and return an ordered id->record dict."""
    out = {}
    for prod in _products():
        pt = prod.get("product_type", "")
        ind = prod.get("industry", "")
        for set_name, kw in keyword_sets(prod):
            res = ds.compose(_Args(pt, ind, kw, ranker))
            out["%s|%s" % (pt, set_name)] = {
                "product_type": pt,
                "industry": ind,
                "keywords": kw,
                "pattern": res.get("pattern"),
                "style": (res.get("style") or {}).get("name"),
                "palette": (res.get("palette") or {}).get("name"),
                "typography": (res.get("typography") or {}).get("pairing"),
                "fallbacks": res.get("_fallbacks", []),
            }
    return out


def diff(base, cur):
    """Yield (id, dimension, old, new) for every changed style/palette/typography pick."""
    changes = []
    for cid, rec in cur.items():
        b = base.get(cid)
        if not b:
            changes.append((cid, "NEW-INPUT", None, None))
            continue
        for dim in ("style", "palette", "typography", "pattern"):
            if b.get(dim) != rec.get(dim):
                changes.append((cid, dim, b.get(dim), rec.get(dim)))
    return changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ranker", choices=["legacy", "new"], default="legacy")
    ap.add_argument("--out", default=None)
    ap.add_argument("--diff", default=None, help="baseline JSON to diff this run against")
    args = ap.parse_args()

    snap = snapshot(args.ranker)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2, sort_keys=True)
        print("wrote %d records to %s (ranker=%s)" % (len(snap), args.out, args.ranker))
    if args.diff:
        with open(args.diff, encoding="utf-8") as f:
            base = json.load(f)
        ch = diff(base, snap)
        print("\n%d changed picks (ranker=%s vs %s):" % (len(ch), args.ranker, args.diff))
        for cid, dim, old, new in ch:
            print("  %-34s %-11s %s -> %s" % (cid, dim, old, new))
    if not args.out and not args.diff:
        print(json.dumps(snap, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    main()
