"""Tests for the clean-room weighted ranker (scripts/design/match.py) and its wiring
into design_system.py.

Covers (MASTER-PLAN 6.1 moat-safe rollout):
  * concrete mis-rank FIXES -- the legacy raw-overlap path picks a worse row (the RED
    anchor: the mis-rank really exists), the new weighted-IDF path picks the better row;
  * determinism (same input -> identical scores + winner, twice);
  * the honest confidence floor (a no-real-match query is flagged, not silently confident);
  * the tie-margin ambiguity flag (a genuine near-tie is disclosed);
  * the named revert path -- DPS_RANKER=legacy reproduces the captured baseline EXACTLY,
    via both the --ranker arg and the env var.

Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/`, no pip install.
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "design"))
sys.path.insert(0, os.path.join(ROOT, "tests", "fixtures"))
import design_system as ds  # noqa: E402
import match  # noqa: E402
import gen_ranker_baseline as grb  # noqa: E402

DATA = os.path.join(ROOT, "data")
FONTS = ds._load(DATA, "font-pairings.csv")
PALETTES = ds._load(DATA, "color-palettes.csv")
PRODUCTS = {p["product_type"]: p for p in ds._load(DATA, "product-types.csv")}
BASELINE = os.path.join(ROOT, "tests", "fixtures", "ranker_baseline.json")


def typo_pick(product_type, keywords, ranker):
    p = PRODUCTS[product_type]
    row, matched, amb = ds.pick_typography(
        FONTS, p.get("typography_mood"), product_type, ds._tokens(keywords), ranker)
    return row.get("name"), matched, amb


def palette_pick(product_type, keywords, ranker):
    p = PRODUCTS[product_type]
    row, matched, amb = ds.pick_palette(
        PALETTES, p.get("industry"), p.get("palette_mood"), ds._tokens(keywords), ranker)
    return row.get("name"), matched, amb


class MisRankFixTest(unittest.TestCase):
    """Each case: legacy picks the WORSE row (RED anchor -- the mis-rank exists), the new
    ranker picks the BETTER, on-mood row (GREEN -- the fix)."""

    def test_agency_portfolio_typography(self):
        # legacy: "precise" tied tech-precise & swiss-objective, CSV order gave the wrong
        # (developer-tool) face. new: difflib "portfolio"~"portfolios" + mood "objective;
        # precise" wins the intended agency face.
        self.assertEqual(typo_pick("agency-portfolio", "", "legacy")[0], "tech-precise")
        self.assertEqual(typo_pick("agency-portfolio", "", "new")[0], "swiss-objective")

    def test_mobile_app_landing_typography(self):
        # new: clean-geometric best_for "mobile-apps" matches the product type; legacy missed it.
        self.assertEqual(typo_pick("mobile-app-landing", "", "legacy")[0], "bold-startup")
        self.assertEqual(typo_pick("mobile-app-landing", "", "new")[0], "clean-geometric")

    def test_restaurant_typography_idf_beats_generic_modern(self):
        # legacy: generic "modern" (from keywords) made modern-neutral win. new: IDF
        # down-weights "modern" so the rare on-brand "warm" wins warm-humanist.
        self.assertEqual(typo_pick("restaurant", "modern, minimal", "legacy")[0], "modern-neutral")
        self.assertEqual(typo_pick("restaurant", "modern, minimal", "new")[0], "warm-humanist")

    def test_personal_brand_palette_idf(self):
        # legacy: "bold"+"creative" tied editorial+ink, CSV order won creative-bold-magenta.
        # new: rarer, on-mood "editorial-ink" palette wins (the product's stated palette_mood).
        self.assertEqual(palette_pick("personal-brand", "bold, premium", "legacy")[0],
                         "creative-bold-magenta")
        self.assertEqual(palette_pick("personal-brand", "bold, premium", "new")[0],
                         "media-editorial-ink")

    def test_new_pick_differs_from_legacy(self):
        for pt, kw in [("agency-portfolio", ""), ("mobile-app-landing", ""),
                       ("restaurant", "modern, minimal")]:
            self.assertNotEqual(typo_pick(pt, kw, "legacy")[0], typo_pick(pt, kw, "new")[0])


class DeterminismTest(unittest.TestCase):
    def test_match_rank_is_deterministic(self):
        q = ds._tokens("modern, trustworthy, minimal")
        r1 = match.rank(FONTS, q, ds.TYPO_WEIGHTS)
        r2 = match.rank(FONTS, q, ds.TYPO_WEIGHTS)
        self.assertEqual(r1.index, r2.index)
        self.assertEqual(r1.scores, r2.scores)
        self.assertEqual(r1.row.get("name"), r2.row.get("name"))

    def test_compose_is_deterministic(self):
        a = grb._Args("saas-landing", "saas", "modern, trustworthy, minimal", "new")
        self.assertEqual(json.dumps(ds.compose(a), sort_keys=True),
                         json.dumps(ds.compose(a), sort_keys=True))


class ConfidenceFloorTest(unittest.TestCase):
    def test_no_real_match_is_flagged_weak(self):
        rr = match.rank(FONTS, {"zzqqxx", "noooop", "qwertyz"}, ds.TYPO_WEIGHTS)
        self.assertFalse(rr.matched, "a no-overlap query must fall below the confidence floor")
        self.assertEqual(rr.score, 0.0)

    def test_real_match_clears_floor(self):
        rr = match.rank(FONTS, ds._tokens("modern clean saas"), ds.TYPO_WEIGHTS)
        self.assertTrue(rr.matched)
        self.assertGreaterEqual(rr.score, match.CONFIDENCE_FLOOR)

    def test_floor_sits_above_palette_aa_bonus(self):
        # so a tie-break bonus can never by itself promote a no-keyword-match palette.
        self.assertGreater(match.CONFIDENCE_FLOOR, ds.AA_BONUS)

    def test_pick_typography_reports_weak_match(self):
        row, matched, _ = ds.pick_typography(FONTS, None, "zzznotathing", {"qwzzx"}, "new")
        self.assertIsNotNone(row)            # still returns a closest row (never None on data)
        self.assertFalse(matched)            # but honestly flags it as weak


class TieMarginTest(unittest.TestCase):
    def test_genuine_near_tie_is_flagged_ambiguous(self):
        # saas-landing typography: clean-geometric edges modern-neutral by ~2% -> ambiguous.
        q = ds._tokens("modern, trustworthy, minimal") | ds._tokens("modern;clean") | ds._tokens("saas-landing")
        rr = match.rank(FONTS, q, ds.TYPO_WEIGHTS)
        self.assertTrue(rr.ambiguous)
        self.assertIsNotNone(rr.runner_up)
        self.assertLess(rr.score - rr.runner_up, match.TIE_MARGIN * rr.score)

    def test_tie_margin_param_controls_the_flag(self):
        q = ds._tokens("modern, trustworthy, minimal") | ds._tokens("modern;clean") | ds._tokens("saas-landing")
        # a near-zero margin must NOT flag the same ~2% gap as ambiguous
        self.assertFalse(match.rank(FONTS, q, ds.TYPO_WEIGHTS, tie_margin=0.001).ambiguous)

    def test_compose_discloses_the_near_tie(self):
        a = grb._Args("saas-landing", "saas", "modern, trustworthy, minimal", "new")
        fbs = ds.compose(a)["_fallbacks"]
        self.assertTrue(any("typography: top matches were close" in fb for fb in fbs),
                        "the golden case should honestly disclose the typography near-tie")


class LegacyRevertTest(unittest.TestCase):
    def test_legacy_reproduces_the_committed_baseline_exactly(self):
        with open(BASELINE, encoding="utf-8") as f:
            base = json.load(f)
        self.assertEqual(grb.snapshot("legacy"), base,
                         "DPS_RANKER=legacy must reproduce the captured baseline byte-for-byte")

    def test_new_default_actually_changes_something(self):
        with open(BASELINE, encoding="utf-8") as f:
            base = json.load(f)
        self.assertNotEqual(grb.snapshot("new"), base,
                            "the new default should differ from the legacy baseline somewhere")

    def test_env_var_selects_legacy(self):
        self.assertEqual(ds._resolve_ranker(None), "new")            # default
        old = os.environ.get("DPS_RANKER")
        try:
            os.environ["DPS_RANKER"] = "legacy"
            self.assertEqual(ds._resolve_ranker(None), "legacy")     # env override
            self.assertEqual(ds._resolve_ranker("new"), "new")       # explicit arg wins over env
        finally:
            if old is None:
                os.environ.pop("DPS_RANKER", None)
            else:
                os.environ["DPS_RANKER"] = old

    def test_env_var_drives_compose(self):
        old = os.environ.get("DPS_RANKER")
        try:
            os.environ["DPS_RANKER"] = "legacy"
            a = grb._Args("restaurant", "food-bev", "modern, minimal", None)  # no explicit ranker
            self.assertEqual(ds.compose(a)["typography"]["pairing"], "modern-neutral")  # legacy pick
        finally:
            if old is None:
                os.environ.pop("DPS_RANKER", None)
            else:
                os.environ["DPS_RANKER"] = old


if __name__ == "__main__":
    unittest.main()
