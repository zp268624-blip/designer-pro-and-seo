"""W3b DESIGN flagship-depth acceptance tests — the design-charts capability.

Pins the chart recommender (scripts/design/gen_charts.py) + its data-shape -> chart
library (data/chart-types.csv) and the design-build wiring:

  * the CSV is well-formed: our own 9-column schema, every a11y_grade in {A,B,C},
    min_series <= max_series, integer volume thresholds, and a row count clear of
    every recorded inspiration band (C-COUNT is enforced separately by the gate);
  * recommend() maps a data SHAPE (+ series/points volume) to a chart with an
    a11y grade + fallback, deterministically and offline;
  * a volume that overflows a shape's band is DISCLOSED (never silently mis-charted)
    and points at the fallback;
  * series-color accessibility REUSES gen_palettes' WCAG luminance/contrast math;
  * the CLI contract: JSON by default, ASCII --human, bad input (unknown shape /
    argparse failure) -> JSON {error} + non-zero, and `-h` exits 0;
  * design-build cites the earned chart-selection reference by exact path (C1).

Runs under both `py -m unittest discover -s tests` and `pytest tests/`, no pip install.
"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "design"))
import gen_charts as gc  # noqa: E402
import gen_palettes as gp  # noqa: E402

CSV = os.path.join(ROOT, "data", "chart-types.csv")
SCRIPT = os.path.join(ROOT, "scripts", "design", "gen_charts.py")
EXPECTED_COLS = ["data_shape", "chart_type", "best_for", "min_series", "max_series",
                 "max_points", "a11y_grade", "a11y_fallback", "notes"]

# Every distinct real on-disk inspiration row count (from .cleanroom-thirdparty); our
# CSV row count must be clear of every +/-2 band. Duplicated here so the test is a hard,
# self-contained clean-room guard even without the gitignored record present.
INSPIRATION_COUNTS = {25, 27, 30, 34, 44, 49, 50, 51, 52, 53, 55, 58, 60,
                      73, 84, 99, 104, 105, 161, 1757, 1760, 1923}


def _rows():
    return gc.load_chart_types(os.path.join(ROOT, "data"))


class ChartCsvTest(unittest.TestCase):
    def test_header_is_our_own_schema(self):
        with open(CSV, newline="", encoding="utf-8-sig") as f:
            import csv
            header = next(csv.reader(f))
        self.assertEqual([c.strip() for c in header], EXPECTED_COLS)

    def test_row_count_clears_every_inspiration_band(self):
        n = len(_rows())
        for c in INSPIRATION_COUNTS:
            self.assertGreater(abs(n - c), 2,
                               "row count %d within +/-2 of inspiration count %d" % (n, c))

    def test_grades_and_thresholds_are_valid(self):
        for r in _rows():
            self.assertIn(r["a11y_grade"], ("A", "B", "C"), r["data_shape"])
            mn, mx, mp = int(r["min_series"]), int(r["max_series"]), int(r["max_points"])
            self.assertLessEqual(mn, mx, "min>max series for %s" % r["data_shape"])
            self.assertGreaterEqual(mn, 1)
            self.assertGreater(mp, 0)
            self.assertTrue(r["chart_type"] and r["a11y_fallback"] and r["best_for"])

    def test_shapes_are_unique_enough_to_route(self):
        # data_shape is the routing key; it must be a non-empty slug per row.
        shapes = [r["data_shape"] for r in _rows()]
        self.assertTrue(all(s and " " not in s for s in shapes))


class RecommendTest(unittest.TestCase):
    def setUp(self):
        self.rows = _rows()

    def test_single_time_series_gets_a_line(self):
        rec = gc.recommend("time-series-single", 1, None, self.rows)
        self.assertEqual(rec["recommended"]["chart_type"], "line")
        self.assertFalse(rec.get("volume_warning"))

    def test_many_categories_go_horizontal(self):
        rec = gc.recommend("category-compare-many", 1, 30, self.rows)
        self.assertEqual(rec["recommended"]["chart_type"], "bar-horizontal")

    def test_volume_overflow_is_disclosed_and_points_at_fallback(self):
        # time-series-multi tops out at a few series; 12 series overflows its band.
        rec = gc.recommend("time-series-multi", 12, None, self.rows)
        self.assertTrue(rec.get("volume_warning"),
                        "an out-of-band series count must be disclosed, not silently charted")
        self.assertTrue(rec["recommended"]["a11y_fallback"])

    def test_recommendation_carries_an_a11y_grade(self):
        rec = gc.recommend("part-to-whole-few", 1, None, self.rows)
        self.assertIn(rec["recommended"]["a11y_grade"], ("A", "B", "C"))
        self.assertTrue(rec["recommended"]["a11y_fallback"])

    def test_unknown_shape_raises(self):
        with self.assertRaises(gc.ChartError):
            gc.recommend("qwerty-nonsense-zzz", 1, None, self.rows)

    def test_lone_generic_token_does_not_match(self):
        # "shape" alone must not route to distribution-shape (too loose a match).
        with self.assertRaises(gc.ChartError):
            gc.recommend("shape", 1, None, self.rows)

    def test_family_token_groups_variants(self):
        # a bare family slug routes within the family (time-series-* here).
        rec = gc.recommend("time-series", 1, None, self.rows)
        self.assertTrue(rec["recommended"]["data_shape"].startswith("time-series"))

    def test_recommend_is_deterministic(self):
        a = gc.recommend("distribution-compare", 4, 500, self.rows)
        b = gc.recommend("distribution-compare", 4, 500, self.rows)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


class SeriesColorA11yTest(unittest.TestCase):
    def test_reuses_gen_palettes_contrast_math(self):
        # the module must lean on gen_palettes' WCAG luminance, not a private copy.
        rep = gc.series_color_a11y(["#08306b", "#7f2704"], "#ffffff")
        self.assertAlmostEqual(rep["colors"][0]["bg_contrast"],
                               gp.contrast_ratio("#08306b", "#ffffff"), places=2)

    def test_low_contrast_palette_grades_c(self):
        rep = gc.series_color_a11y(["#ffff00", "#ffffff"], "#ffffff")
        self.assertEqual(rep["grade"], "C")
        self.assertTrue(rep["needs"], "a failing palette must list what to fix")

    def test_dark_distinct_palette_passes_background(self):
        rep = gc.series_color_a11y(["#08306b", "#7f2704"], "#ffffff")
        self.assertTrue(rep["bg_all_pass"])

    def test_nonadjacent_near_identical_downgrades_from_A(self):
        # #08306b (idx 0) and #0a326d (idx 2) are near-identical but NON-adjacent; the two
        # ADJACENT pairs each clear 3:1 (3.7 and 3.6) and every series clears the white bg,
        # so an ADJACENT-ONLY grade would wrongly say A. Full-pairwise grading must catch
        # the confusable non-adjacent pair (1.03:1) and downgrade to B.
        rep = gc.series_color_a11y(["#08306b", "#8a8a8a", "#0a326d"], "#ffffff")
        self.assertTrue(rep["bg_all_pass"])
        self.assertEqual(rep["grade"], "B",
                         "a near-identical NON-adjacent series pair must downgrade, not stay A")
        self.assertFalse(rep["pairs_all_pass"])
        bad = [p for p in rep["pairs"] if not p["distinct"]]
        self.assertTrue(bad and all(not p["adjacent"] for p in bad),
                        "the only failing pair here is the non-adjacent one")
        self.assertTrue(rep["needs"], "a downgraded palette must list what to fix")

    def test_wellseparated_set_stays_A(self):
        # Every series clears the background AND every pair clears 3:1 -> grade A holds.
        rep = gc.series_color_a11y(["#08306b", "#8a8a8a"], "#ffffff")
        self.assertEqual(rep["grade"], "A")
        self.assertTrue(rep["pairs_all_pass"] and rep["bg_all_pass"])

    def test_grades_full_pairwise_set_not_just_adjacent(self):
        # n colors -> n*(n-1)/2 unordered pairs graded, with adjacent kept as a subset.
        rep = gc.series_color_a11y(["#000000", "#333333", "#666666", "#999999"], "#ffffff")
        self.assertEqual(len(rep["pairs"]), 6)
        self.assertEqual(len(rep["adjacent_pairs"]), 3)
        self.assertTrue(all(p["adjacent"] for p in rep["adjacent_pairs"]))


class CliContractTest(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args],
                              capture_output=True, encoding="utf-8")

    def test_json_by_default(self):
        r = self._run("--shape", "scatter-correlation", "--series", "1")
        # scatter shape slug is 'two-var-correlation'; use the real slug:
        r = self._run("--shape", "two-var-correlation", "--series", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertIn("recommended", d)

    def test_human_is_ascii(self):
        r = self._run("--shape", "time-series-single", "--human")
        self.assertEqual(r.returncode, 0, r.stderr)
        r.stdout.encode("ascii")  # raises if non-ASCII leaked

    def test_unknown_shape_is_json_error_nonzero(self):
        r = self._run("--shape", "totally-made-up", "--series", "1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("error", json.loads(r.stdout))

    def test_argparse_failure_is_json_error_nonzero(self):
        r = self._run("--shape", "time-series-single", "--series", "not-an-int")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("error", json.loads(r.stdout))

    def test_help_exits_zero(self):
        r = self._run("-h")
        self.assertEqual(r.returncode, 0)

    def test_spec_json_path(self):
        r = self._run("--spec", "-")
        # feed a spec on stdin
        r = subprocess.run([sys.executable, SCRIPT, "--spec", "-"],
                           input=json.dumps({"shape": "time-series-single", "series": 1}),
                           capture_output=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["recommended"]["chart_type"], "line")


class DesignBuildWiringTest(unittest.TestCase):
    def test_design_build_cites_chart_reference_by_exact_path(self):
        with open(os.path.join(ROOT, "skills", "design-build", "SKILL.md"),
                  encoding="utf-8") as f:
            body = f.read()
        self.assertIn("references/design-build/chart-selection.md", body)
        self.assertIn("gen_charts.py", body)

    def test_chart_reference_exists_and_is_lean(self):
        p = os.path.join(ROOT, "references", "design-build", "chart-selection.md")
        self.assertTrue(os.path.exists(p))
        with open(p, encoding="utf-8") as f:
            self.assertLessEqual(len(f.read().splitlines()), 210)


if __name__ == "__main__":
    unittest.main()
