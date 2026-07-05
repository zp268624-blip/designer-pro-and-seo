"""Tests for the seo-local-unified flagship leaf scripts (Wave 3a):

  scripts/seo/nap_check.py  -- NAP (name/address/phone) consistency checker over
                               supplied listings; normalizes + diffs + flags.
  scripts/seo/geogrid.py    -- Share-of-Local-Voice (SoLV) geo-grid math + a
                               center+radius grid builder.

Contract (both): JSON to stdout by default; `--human` ASCII summary; deterministic
(same input -> same output); bad input -> JSON error object + a NON-ZERO exit (never
a raw traceback); offline (`--grid` / `--listings` / `--no-network`) exits 0 and
touches no network. Any URL fetch routes through the shared SSRF guard
(`net_safety.safe_open`).

Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/`, no pip
install, no network. Fixtures live in a tempdir.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEO = os.path.join(ROOT, "scripts", "seo")
NAP = os.path.join(SEO, "nap_check.py")
GEOGRID = os.path.join(SEO, "geogrid.py")


def _run(script_path, args):
    proc = subprocess.run(
        [sys.executable, script_path] + args,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _is_ascii(text):
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _write(tmp, name, obj):
    p = os.path.join(tmp, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return p


# --------------------------------------------------------------------------- #
# Shared SSRF-guard contract: both scripts import net_safety (the one guard).
# --------------------------------------------------------------------------- #
class SsrfImportTest(unittest.TestCase):
    def test_both_scripts_import_the_shared_guard(self):
        for path in (NAP, GEOGRID):
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            self.assertIn("net_safety", src,
                          "%s must route fetches through net_safety" % path)
            self.assertIn("safe_open", src,
                          "%s must fetch via the shared safe_open" % path)


# --------------------------------------------------------------------------- #
# geogrid.py -- SoLV math
# --------------------------------------------------------------------------- #
class GeogridSolvTest(unittest.TestCase):
    # ranks 1, 4, not-found -> visibility 1.0, 0.25, 0.0 ; mean = 0.41666.. -> 41.67%
    GRID = {
        "business": "Acme Plumbing",
        "keyword": "emergency plumber",
        "depth": 20,
        "points": [
            {"lat": 40.00, "lng": -111.00, "rank": 1},
            {"lat": 40.01, "lng": -111.00, "rank": 4},
            {"lat": 40.02, "lng": -111.00, "rank": None},
        ],
    }

    def _solv(self, grid, extra=None):
        tmp = tempfile.mkdtemp(prefix="dps_geo_")
        self.addCleanup(_rmtree, tmp)
        p = _write(tmp, "grid.json", grid)
        return _run(GEOGRID, ["--grid", p] + (extra or []))

    def test_solv_math_on_known_grid(self):
        rc, out, err = self._solv(self.GRID)
        self.assertEqual(rc, 0, err)
        d = json.loads(out)
        self.assertTrue(d["ok"])
        self.assertEqual(d["grid_points"], 3)
        self.assertEqual(d["found_points"], 2)
        self.assertAlmostEqual(d["solv_percent"], 41.67, places=2)
        self.assertAlmostEqual(d["coverage_percent"], 66.67, places=2)
        self.assertAlmostEqual(d["top3_percent"], 33.33, places=2)
        self.assertAlmostEqual(d["avg_rank_found"], 2.5, places=2)
        self.assertEqual(d["best_rank"], 1)
        self.assertEqual(d["worst_rank"], 4)

    def test_deterministic(self):
        rc1, out1, _ = self._solv(self.GRID)
        rc2, out2, _ = self._solv(self.GRID)
        self.assertEqual((rc1, out1), (rc2, out2))

    def test_offline_grid_exits_zero(self):
        rc, out, err = self._solv(self.GRID, ["--no-network"])
        self.assertEqual(rc, 0, err)
        self.assertTrue(json.loads(out)["ok"])

    def test_human_is_ascii(self):
        rc, out, err = self._solv(self.GRID, ["--human"])
        self.assertEqual(rc, 0, err)
        self.assertTrue(_is_ascii(out))

    def test_weighted_solv(self):
        # weight the not-found point heavily -> SoLV drops below the unweighted 41.67
        grid = json.loads(json.dumps(self.GRID))
        grid["points"][0]["weight"] = 1.0
        grid["points"][1]["weight"] = 1.0
        grid["points"][2]["weight"] = 8.0
        rc, out, err = self._solv(grid)
        self.assertEqual(rc, 0, err)
        d = json.loads(out)
        self.assertTrue(d["weighted"])
        # (1.0*1 + 0.25*1 + 0.0*8) / 10 * 100 = 12.5
        self.assertAlmostEqual(d["solv_percent"], 12.5, places=2)

    def test_empty_points_is_error(self):
        rc, out, _ = self._solv({"points": []})
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["ok"])

    def test_bad_rank_is_error(self):
        rc, out, _ = self._solv({"points": [{"lat": 1, "lng": 2, "rank": "nope"}]})
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["ok"])

    def test_bad_coord_is_error(self):
        rc, out, _ = self._solv({"points": [{"lat": "x", "lng": 2, "rank": 1}]})
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["ok"])

    def test_no_input_is_error(self):
        rc, out, _ = _run(GEOGRID, [])
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["ok"])

    def test_unparseable_file_is_error(self):
        tmp = tempfile.mkdtemp(prefix="dps_geo_")
        self.addCleanup(_rmtree, tmp)
        p = os.path.join(tmp, "bad.json")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        rc, out, _ = _run(GEOGRID, ["--grid", p])
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["ok"])


# --------------------------------------------------------------------------- #
# geogrid.py -- center+radius grid builder
# --------------------------------------------------------------------------- #
class GeogridBuildTest(unittest.TestCase):
    def _build(self, extra):
        return _run(GEOGRID, ["--build-grid"] + extra)

    def test_build_grid_from_center_offline(self):
        rc, out, err = self._build(
            ["--center", "40.0,-111.0", "--radius", "2", "--size", "3", "--no-network"])
        self.assertEqual(rc, 0, err)
        d = json.loads(out)
        self.assertTrue(d["ok"])
        self.assertEqual(d["grid_points"], 9)
        self.assertEqual(d["size"], 3)
        self.assertAlmostEqual(d["step_km"], 2.0, places=6)
        # the middle point of a 3x3 grid is the exact center
        mid = d["points"][4]
        self.assertAlmostEqual(mid["lat"], 40.0, places=6)
        self.assertAlmostEqual(mid["lng"], -111.0, places=6)
        # every built point starts un-ranked
        self.assertTrue(all(p["rank"] is None for p in d["points"]))

    def test_build_grid_deterministic(self):
        a = self._build(["--center", "40.0,-111.0", "--radius", "2", "--size", "5",
                         "--no-network"])
        b = self._build(["--center", "40.0,-111.0", "--radius", "2", "--size", "5",
                         "--no-network"])
        self.assertEqual(a, b)

    def test_build_grid_needs_center_or_geocode(self):
        rc, out, _ = self._build(["--radius", "2", "--size", "3"])
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["ok"])

    def test_geocode_offline_is_error(self):
        # --geocode requires network; --no-network must refuse, never hang.
        rc, out, _ = self._build(
            ["--geocode", "Provo, UT", "--radius", "2", "--size", "3", "--no-network"])
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["ok"])

    def test_bad_center_is_error(self):
        rc, out, _ = self._build(["--center", "not-a-coord", "--no-network"])
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["ok"])


# --------------------------------------------------------------------------- #
# nap_check.py -- NAP consistency
# --------------------------------------------------------------------------- #
class NapCheckTest(unittest.TestCase):
    # website (primary) vs three citations. search-directory + social-directory
    # normalize EQUAL to the canonical (formatting-only differences); review-directory
    # carries a DIFFERENT phone number.
    LISTINGS = {
        "business": "Acme Plumbing",
        "listings": [
            {"source": "website", "name": "Acme Plumbing LLC",
             "address": "123 Main St, Suite 200", "phone": "(801) 555-0199",
             "primary": True},
            {"source": "search-directory", "name": "Acme Plumbing LLC",
             "address": "123 Main Street Ste 200", "phone": "801-555-0199"},
            {"source": "review-directory", "name": "Acme Plumbing LLC",
             "address": "123 Main St #200", "phone": "801-555-0142"},
            {"source": "social-directory", "name": "Acme Plumbing LLC",
             "address": "123 Main St Suite 200", "phone": "+1 801 555 0199",
             "url": "https://example.com/contact"},
        ],
    }

    def _check(self, listings, extra=None):
        tmp = tempfile.mkdtemp(prefix="dps_nap_")
        self.addCleanup(_rmtree, tmp)
        p = _write(tmp, "listings.json", listings)
        return _run(NAP, ["--listings", p] + (extra or []))

    def test_detects_phone_inconsistency(self):
        rc, out, err = self._check(self.LISTINGS)
        self.assertEqual(rc, 0, err)
        d = json.loads(out)
        self.assertTrue(d["ok"])
        self.assertFalse(d["consistent"], "a divergent phone must make NAP inconsistent")
        # exactly one HIGH phone finding, on review-directory
        phone_finds = [f for f in d["findings"] if f["field"] == "phone"]
        self.assertEqual(len(phone_finds), 1)
        self.assertEqual(phone_finds[0]["source"], "review-directory")
        self.assertEqual(phone_finds[0]["severity"], "HIGH")
        # the phone field is flagged inconsistent; name + address normalize equal
        self.assertFalse(d["fields"]["phone"]["consistent"])
        self.assertTrue(d["fields"]["address"]["consistent"],
                        "St/Street/Ste/#/Suite must normalize to one address")
        self.assertTrue(d["fields"]["name"]["consistent"])

    def test_all_consistent_when_only_formatting_differs(self):
        listings = json.loads(json.dumps(self.LISTINGS))
        # fix review-directory's phone so every listing agrees after normalization
        listings["listings"][2]["phone"] = "801.555.0199"
        rc, out, err = self._check(listings)
        self.assertEqual(rc, 0, err)
        d = json.loads(out)
        self.assertTrue(d["consistent"])
        self.assertEqual(d["findings"], [])

    def test_offline_exits_zero(self):
        rc, out, err = self._check(self.LISTINGS, ["--no-network"])
        self.assertEqual(rc, 0, err)
        self.assertTrue(json.loads(out)["ok"])

    def test_human_is_ascii(self):
        rc, out, err = self._check(self.LISTINGS, ["--human"])
        self.assertEqual(rc, 0, err)
        self.assertTrue(_is_ascii(out))

    def test_canonical_selection_by_source(self):
        rc, out, err = self._check(self.LISTINGS, ["--canonical", "search-directory"])
        self.assertEqual(rc, 0, err)
        d = json.loads(out)
        self.assertEqual(d["canonical"]["source"], "search-directory")

    def test_empty_listings_is_error(self):
        rc, out, _ = self._check({"listings": []})
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["ok"])

    def test_no_input_is_error(self):
        rc, out, _ = _run(NAP, [])
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["ok"])

    def test_unparseable_file_is_error(self):
        tmp = tempfile.mkdtemp(prefix="dps_nap_")
        self.addCleanup(_rmtree, tmp)
        p = os.path.join(tmp, "bad.json")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("not json at all")
        rc, out, _ = _run(NAP, ["--listings", p])
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["ok"])

    def test_listing_missing_nap_is_error(self):
        rc, out, _ = self._check({"listings": [{"source": "x"}]})
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["ok"])


class ArgparseContractTest(unittest.TestCase):
    """FIX 2: argparse's own failures must degrade to JSON {"error"} on stdout + a
    non-zero exit, never a bare usage dump to stderr."""
    def test_geogrid_bad_typed_arg_is_json_error(self):
        # --size expects an int; a bad value is an argparse failure.
        rc, out, err = _run(GEOGRID, ["--build-grid", "--center", "40,-111",
                                      "--size", "not-an-int"])
        self.assertNotEqual(rc, 0)
        data = json.loads(out)
        self.assertIn("error", data)
        self.assertTrue(_is_ascii(out))

    def test_nap_bad_typed_arg_is_json_error(self):
        # --timeout expects a float; a bad value is an argparse failure.
        rc, out, err = _run(NAP, ["--listings", "x.json", "--timeout", "soon"])
        self.assertNotEqual(rc, 0)
        data = json.loads(out)
        self.assertIn("error", data)
        self.assertTrue(_is_ascii(out))


def _rmtree(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
