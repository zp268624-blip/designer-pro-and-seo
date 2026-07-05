"""seo-drift SQLite engine + severity tests (Wave-3a flagship depth).

Three layers under test, all OFFLINE (local HTML fixtures, no network):

  * drift_severity.evaluate  -- the change->severity engine whose rules are DERIVED
    from exactly which on-page elements drift_tools.capture() records (3 tiers:
    critical / high / advisory). A changed element must yield the right tier.
  * drift_baseline -> drift_compare roundtrip -- capture a snapshot into a local
    SQLite db, then compare a fresh capture against the stored baseline.
  * drift_history -- list/trend the stored baselines.

Bad input (no --file/--url, missing db, no baseline) must exit non-zero with a JSON
error. Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/`, no pip
install, no network.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEO = os.path.join(ROOT, "scripts", "seo")
sys.path.insert(0, SEO)
sys.path.insert(0, os.path.join(ROOT, "scripts", "workflow"))

import drift_severity  # noqa: E402  (RED until the module is authored)

BASELINE = os.path.join(SEO, "drift_baseline.py")
COMPARE = os.path.join(SEO, "drift_compare.py")
HISTORY = os.path.join(SEO, "drift_history.py")
SEVERITY = os.path.join(SEO, "drift_severity.py")


# --- fixtures: a baseline page and several single-change mutations ------------------
_A = """<html><head>
<title>Original Title</title>
<meta name="description" content="The original meta description text">
<link rel="canonical" href="https://ex.com/a">
<meta name="robots" content="index,follow">
<meta property="og:title" content="OG Original">
<script type="application/ld+json">{"@type":"Article"}</script>
</head><body>
<h1>Original H1</h1><h2>Section</h2>
<p>%s</p>
</body></html>""" % (" ".join(["word"] * 120))

# title changed + robots gains noindex + canonical flipped + the JSON-LD block removed
_B = """<html><head>
<title>A Completely New Title</title>
<meta name="description" content="The original meta description text">
<link rel="canonical" href="https://ex.com/b">
<meta name="robots" content="noindex,follow">
<meta property="og:title" content="OG Original">
</head><body>
<h1>Original H1</h1><h2>Section</h2>
<p>%s</p>
</body></html>""" % (" ".join(["word"] * 120))


def _snap(html):
    import drift_tools
    return drift_tools.capture(html, url="https://ex.com/a")


def _run(script, args, cwd=None):
    proc = subprocess.run([sys.executable, script] + args, capture_output=True,
                          text=True, cwd=cwd)
    try:
        obj = json.loads(proc.stdout)
    except (ValueError, json.JSONDecodeError):
        obj = None
    return proc.returncode, obj, proc.stdout, proc.stderr


class SeverityEngineTest(unittest.TestCase):
    """Each rule maps a specific captured-element change to our own 3-tier model."""

    def _sev_for(self, result, element):
        return {c["element"]: c["severity"] for c in result["regressions"]}.get(element)

    def test_noindex_gain_is_critical(self):
        base = {"meta_robots": "index,follow"}
        cur = {"meta_robots": "noindex,follow"}
        r = drift_severity.evaluate(base, cur)
        self.assertEqual(self._sev_for(r, "meta_robots"), "critical")

    def test_nofollow_gain_is_critical(self):
        r = drift_severity.evaluate({"meta_robots": "index,follow"},
                                    {"meta_robots": "index,nofollow"})
        self.assertEqual(self._sev_for(r, "meta_robots"), "critical")

    def test_robots_other_change_is_high_not_critical(self):
        # losing a directive (no noindex/nofollow gained) is serious but not deindexing
        r = drift_severity.evaluate({"meta_robots": "index,follow,max-snippet:-1"},
                                    {"meta_robots": "index,follow"})
        self.assertEqual(self._sev_for(r, "meta_robots"), "high")

    def test_title_change_is_high(self):
        r = drift_severity.evaluate({"title": "Old"}, {"title": "New"})
        self.assertEqual(self._sev_for(r, "title"), "high")

    def test_h1_change_is_high(self):
        r = drift_severity.evaluate({"h1": "Old"}, {"h1": "New"})
        self.assertEqual(self._sev_for(r, "h1"), "high")

    def test_canonical_flip_is_critical(self):
        r = drift_severity.evaluate({"canonical": "https://ex.com/a"},
                                    {"canonical": "https://ex.com/b"})
        self.assertEqual(self._sev_for(r, "canonical"), "critical")

    def test_canonical_drop_is_critical(self):
        r = drift_severity.evaluate({"canonical": "https://ex.com/a"},
                                    {"canonical": None})
        self.assertEqual(self._sev_for(r, "canonical"), "critical")

    def test_canonical_add_is_advisory(self):
        r = drift_severity.evaluate({"canonical": None},
                                    {"canonical": "https://ex.com/a"})
        self.assertEqual(self._sev_for(r, "canonical"), "advisory")

    def test_schema_loss_is_high(self):
        r = drift_severity.evaluate({"schema_blocks": 2}, {"schema_blocks": 0})
        self.assertEqual(self._sev_for(r, "schema_blocks"), "high")

    def test_schema_gain_is_advisory(self):
        r = drift_severity.evaluate({"schema_blocks": 1}, {"schema_blocks": 3})
        self.assertEqual(self._sev_for(r, "schema_blocks"), "advisory")

    def test_meta_description_change_is_advisory(self):
        r = drift_severity.evaluate({"meta_description": "a"}, {"meta_description": "b"})
        self.assertEqual(self._sev_for(r, "meta_description"), "advisory")

    def test_word_count_within_noise_is_ignored(self):
        r = drift_severity.evaluate({"word_count": 1000}, {"word_count": 1050})
        self.assertIsNone(self._sev_for(r, "word_count"))

    def test_word_count_beyond_noise_is_advisory(self):
        r = drift_severity.evaluate({"word_count": 1000}, {"word_count": 500})
        self.assertEqual(self._sev_for(r, "word_count"), "advisory")

    def test_no_change_yields_empty(self):
        snap = _snap(_A)
        r = drift_severity.evaluate(snap, snap)
        self.assertEqual(r["changed"], 0)
        self.assertEqual(r["regressions"], [])

    def test_results_sorted_critical_first(self):
        r = drift_severity.evaluate(_snap(_A), _snap(_B))
        sevs = [c["severity"] for c in r["regressions"]]
        order = {"critical": 0, "high": 1, "advisory": 2}
        self.assertEqual(sevs, sorted(sevs, key=lambda s: order[s]))

    def test_every_change_carries_a_rule_code_and_note(self):
        r = drift_severity.evaluate(_snap(_A), _snap(_B))
        self.assertTrue(r["regressions"])
        for c in r["regressions"]:
            self.assertTrue(c.get("code"), "every change carries a rule code")
            self.assertTrue(c.get("note"), "every change carries a plain-language note")


class _DbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dps_drift_")
        self.db = os.path.join(self.tmp, "baselines.db")
        self.fa = os.path.join(self.tmp, "a.html")
        self.fb = os.path.join(self.tmp, "b.html")
        with open(self.fa, "w", encoding="utf-8") as f:
            f.write(_A)
        with open(self.fb, "w", encoding="utf-8") as f:
            f.write(_B)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)


class BaselineCompareRoundtripTest(_DbCase):
    def test_capture_then_compare_detects_the_right_severities(self):
        rc, obj, out, err = _run(BASELINE, ["--file", self.fa, "--db", self.db,
                                            "--url", "https://ex.com/a",
                                            "--label", "prod",
                                            "--captured-at", "2026-06-30T00:00:00+00:00"])
        self.assertEqual(rc, 0, err)
        self.assertEqual(obj["action"], "baseline")
        self.assertTrue(os.path.exists(self.db))

        rc, obj, out, err = _run(COMPARE, ["--file", self.fb, "--db", self.db,
                                           "--url", "https://ex.com/a"])
        self.assertEqual(rc, 0, err)
        sev = {c["element"]: c["severity"] for c in obj["regressions"]}
        self.assertEqual(sev.get("meta_robots"), "critical")   # noindex added
        self.assertEqual(sev.get("canonical"), "critical")     # flipped
        self.assertEqual(sev.get("title"), "high")             # changed
        self.assertEqual(sev.get("schema_blocks"), "high")     # JSON-LD removed

    def test_compare_against_same_capture_reports_no_drift(self):
        _run(BASELINE, ["--file", self.fa, "--db", self.db, "--url", "https://ex.com/a",
                        "--captured-at", "2026-06-30T00:00:00+00:00"])
        rc, obj, out, err = _run(COMPARE, ["--file", self.fa, "--db", self.db,
                                           "--url", "https://ex.com/a"])
        self.assertEqual(rc, 0, err)
        self.assertEqual(obj["changed"], 0)

    def test_compare_by_baseline_id(self):
        rc, obj, _, err = _run(BASELINE, ["--file", self.fa, "--db", self.db,
                                          "--captured-at", "2026-06-30T00:00:00+00:00"])
        bid = obj["id"]
        rc, obj, _, err = _run(COMPARE, ["--file", self.fb, "--db", self.db,
                                         "--baseline-id", str(bid)])
        self.assertEqual(rc, 0, err)
        self.assertGreater(obj["changed"], 0)


class BadInputTest(_DbCase):
    def test_baseline_without_file_or_url_exits_nonzero(self):
        rc, obj, out, err = _run(BASELINE, ["--db", self.db])
        self.assertNotEqual(rc, 0)
        self.assertTrue(obj and "error" in obj, out + err)

    def test_compare_with_missing_db_exits_nonzero(self):
        rc, obj, out, err = _run(COMPARE, ["--file", self.fb,
                                           "--db", os.path.join(self.tmp, "nope.db")])
        self.assertNotEqual(rc, 0)
        self.assertTrue(obj and "error" in obj, out + err)

    def test_compare_with_no_matching_baseline_exits_nonzero(self):
        # db exists (a baseline for a DIFFERENT url) but none matches the requested url
        _run(BASELINE, ["--file", self.fa, "--db", self.db, "--url", "https://ex.com/a",
                        "--captured-at", "2026-06-30T00:00:00+00:00"])
        rc, obj, out, err = _run(COMPARE, ["--file", self.fb, "--db", self.db,
                                           "--label", "does-not-exist"])
        self.assertNotEqual(rc, 0)
        self.assertTrue(obj and "error" in obj, out + err)

    def test_history_with_missing_db_exits_nonzero(self):
        rc, obj, out, err = _run(HISTORY, ["--db", os.path.join(self.tmp, "nope.db")])
        self.assertNotEqual(rc, 0)
        self.assertTrue(obj and "error" in obj, out + err)


class HistoryTest(_DbCase):
    def _seed_two(self):
        _run(BASELINE, ["--file", self.fa, "--db", self.db, "--url", "https://ex.com/a",
                        "--label", "prod", "--captured-at", "2026-06-30T00:00:00+00:00"])
        _run(BASELINE, ["--file", self.fb, "--db", self.db, "--url", "https://ex.com/a",
                        "--label", "prod", "--captured-at", "2026-06-30T01:00:00+00:00"])

    def test_history_lists_stored_baselines(self):
        self._seed_two()
        rc, obj, out, err = _run(HISTORY, ["--db", self.db, "--url", "https://ex.com/a"])
        self.assertEqual(rc, 0, err)
        self.assertEqual(obj["action"], "history")
        self.assertEqual(obj["count"], 2)
        self.assertEqual([b["captured_at"] for b in obj["baselines"]],
                         ["2026-06-30T00:00:00+00:00", "2026-06-30T01:00:00+00:00"])

    def test_history_trend_counts_changes_between_snapshots(self):
        self._seed_two()
        rc, obj, out, err = _run(HISTORY, ["--db", self.db, "--url", "https://ex.com/a",
                                           "--trend"])
        self.assertEqual(rc, 0, err)
        self.assertEqual(obj["action"], "trend")
        self.assertEqual(len(obj["transitions"]), 1)
        t = obj["transitions"][0]
        self.assertGreater(t["changed"], 0)
        self.assertGreaterEqual(t["counts"]["critical"], 2)  # noindex + canonical flip


class DriftArgparseContractTest(unittest.TestCase):
    """FIX 2: argparse failures on the drift CLIs must emit JSON {"error"} + non-zero,
    not a bare usage dump to stderr."""
    def test_severity_missing_required_arg_is_json_error(self):
        rc, obj, out, err = _run(SEVERITY, [])  # --baseline/--current required
        self.assertNotEqual(rc, 0)
        self.assertTrue(obj and "error" in obj, out + err)

    def test_severity_bad_typed_arg_is_json_error(self):
        rc, obj, out, err = _run(SEVERITY, ["--baseline", "a.json", "--current",
                                            "b.json", "--word-noise", "NaNish"])
        self.assertNotEqual(rc, 0)
        self.assertTrue(obj and "error" in obj, out + err)


class PluginRootGuardTest(_DbCase):
    """FIX 5: with no --db and a plugin-root-like cwd (a .claude-plugin/ dir present), the
    store must NOT be created inside the plugin -- it errors instead."""
    def test_baseline_refuses_to_write_inside_plugin(self):
        plugroot = os.path.join(self.tmp, "plugroot")
        os.makedirs(os.path.join(plugroot, ".claude-plugin"))
        page = os.path.join(plugroot, "page.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write(_A)
        rc, obj, out, err = _run(
            BASELINE, ["--file", page, "--captured-at", "2026-06-30T00:00:00+00:00"],
            cwd=plugroot)
        self.assertNotEqual(rc, 0, out + err)
        self.assertTrue(obj and "error" in obj, out + err)
        self.assertFalse(os.path.exists(os.path.join(plugroot, ".seo-drift")),
                         "must not create a drift store inside the plugin")


if __name__ == "__main__":
    unittest.main()
