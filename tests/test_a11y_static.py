"""Wave-3b DESIGN flagship: scripts/design/a11y_static.py -- a stdlib (html.parser)
STRUCTURAL accessibility checker over an HTML file/string -> severity-ranked JSON findings.

Every case is OFFLINE (no network, no key): HTML is inline or a temp file, tokens are a
temp JSON. The checker is deterministic; the same input yields byte-identical output. It
gives `qa-gate` + `design-accessibility` a real artifact (the free Tier-2 path).

Runs under both `py -m unittest discover -s tests` and `pytest tests/`; no pip install.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A11Y = os.path.join(ROOT, "scripts", "design", "a11y_static.py")

sys.path.insert(0, os.path.join(ROOT, "scripts", "design"))
import a11y_static  # noqa: E402


def run(args):
    """Run the CLI; return (returncode, parsed_json_or_None, stdout)."""
    r = subprocess.run([sys.executable, A11Y] + args,
                       capture_output=True, encoding="utf-8")
    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        data = None
    return r.returncode, data, r.stdout


def codes(report):
    return {f["code"] for f in report["findings"]}


# A structurally clean page: html lang, one h1 then h2 (no skip), captioned image,
# labeled input, zoomable viewport, a skip link, and a <main> landmark.
CLEAN = """<!doctype html>
<html lang="en">
<head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body>
<a href="#main">Skip to content</a>
<header><nav>Home</nav></header>
<main id="main">
  <h1>Zephyr Corp cedar benches</h1>
  <h2>How long they last</h2>
  <img src="bench.jpg" alt="A cedar bench on a patio">
  <form>
    <label for="email">Email</label>
    <input id="email" type="email">
  </form>
</main>
<footer>Contact</footer>
</body></html>"""


class CleanPageTest(unittest.TestCase):
    def test_clean_page_has_no_findings(self):
        rep = a11y_static.analyze(CLEAN)
        self.assertEqual(rep["findings"], [], "clean page should trip no findings: %r" % rep["findings"])
        self.assertTrue(rep["clean"])
        self.assertEqual(rep["counts"], {"critical": 0, "serious": 0, "moderate": 0, "minor": 0})

    def test_clean_page_cli_exit_zero(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "clean.html")
            with open(p, "w", encoding="utf-8") as f:
                f.write(CLEAN)
            rc, data, _ = run(["--file", p])
            self.assertEqual(rc, 0)
            self.assertTrue(data["clean"])


class MissingAltTest(unittest.TestCase):
    def test_img_without_alt_trips_serious(self):
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<img src="x.jpg"></main></body></html>')
        self.assertIn("img-missing-alt", codes(rep))
        f = [x for x in rep["findings"] if x["code"] == "img-missing-alt"][0]
        self.assertEqual(f["severity"], "serious")
        self.assertEqual(f["wcag"], "1.1.1")

    def test_empty_alt_is_decorative_and_allowed(self):
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<img src="x.jpg" alt=""></main></body></html>')
        self.assertNotIn("img-missing-alt", codes(rep))


class HeadingOrderTest(unittest.TestCase):
    def test_skipped_level_trips_moderate(self):
        rep = a11y_static.analyze('<html lang="en"><body><main>'
                                  '<h1>A</h1><h3>B</h3></main></body></html>')
        self.assertIn("heading-skip", codes(rep))
        f = [x for x in rep["findings"] if x["code"] == "heading-skip"][0]
        self.assertEqual(f["severity"], "moderate")

    def test_no_skip_when_sequential(self):
        rep = a11y_static.analyze('<html lang="en"><body><main>'
                                  '<h1>A</h1><h2>B</h2><h3>C</h3></main></body></html>')
        self.assertNotIn("heading-skip", codes(rep))

    def test_headings_but_no_h1(self):
        rep = a11y_static.analyze('<html lang="en"><body><main>'
                                  '<h2>A</h2><h3>B</h3></main></body></html>')
        self.assertIn("heading-no-h1", codes(rep))

    def test_multiple_h1_is_minor(self):
        rep = a11y_static.analyze('<html lang="en"><body><main>'
                                  '<h1>A</h1><h1>B</h1></main></body></html>')
        self.assertIn("heading-multiple-h1", codes(rep))
        f = [x for x in rep["findings"] if x["code"] == "heading-multiple-h1"][0]
        self.assertEqual(f["severity"], "minor")


class FormLabelTest(unittest.TestCase):
    def test_unlabeled_control_is_critical(self):
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<input type="text"></main></body></html>')
        self.assertIn("control-no-label", codes(rep))
        f = [x for x in rep["findings"] if x["code"] == "control-no-label"][0]
        self.assertEqual(f["severity"], "critical")

    def test_label_for_satisfies(self):
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<label for="n">Name</label><input id="n"></main></body></html>')
        self.assertNotIn("control-no-label", codes(rep))

    def test_aria_label_satisfies(self):
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<input aria-label="Search"></main></body></html>')
        self.assertNotIn("control-no-label", codes(rep))

    def test_wrapping_label_satisfies(self):
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<label>Name <input type="text"></label></main></body></html>')
        self.assertNotIn("control-no-label", codes(rep))

    def test_hidden_and_submit_are_exempt(self):
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<input type="hidden" name="csrf">'
                                  '<input type="submit" value="Go"></main></body></html>')
        self.assertNotIn("control-no-label", codes(rep))

    def test_placeholder_is_not_a_label(self):
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<input type="text" placeholder="Name"></main></body></html>')
        self.assertIn("control-no-label", codes(rep))

    def test_empty_label_for_is_not_a_name(self):
        # BLOCKER: an EMPTY <label for="x"> carries no accessible name -- the control it
        # points at is still UNLABELED (critical), not a clean pass.
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<label for="x"></label><input id="x"></main></body></html>')
        self.assertIn("control-no-label", codes(rep))
        f = [x for x in rep["findings"] if x["code"] == "control-no-label"][0]
        self.assertEqual(f["severity"], "critical")

    def test_nonempty_label_for_passes(self):
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<label for="x">Full name</label><input id="x"></main></body></html>')
        self.assertNotIn("control-no-label", codes(rep))

    def test_whitespace_only_label_for_is_not_a_name(self):
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<label for="x">   </label><input id="x"></main></body></html>')
        self.assertIn("control-no-label", codes(rep))

    def test_empty_aria_labelledby_target_is_not_a_name(self):
        # An aria-labelledby that resolves to an EMPTY element is not an accessible name.
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<span id="lbl"></span>'
                                  '<input aria-labelledby="lbl"></main></body></html>')
        self.assertIn("control-no-label", codes(rep))

    def test_nonempty_aria_labelledby_target_passes(self):
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<span id="lbl">Search</span>'
                                  '<input aria-labelledby="lbl"></main></body></html>')
        self.assertNotIn("control-no-label", codes(rep))

    def test_empty_wrapping_label_is_not_a_name(self):
        rep = a11y_static.analyze('<html lang="en"><body><main><h1>T</h1>'
                                  '<label><input type="text"></label></main></body></html>')
        self.assertIn("control-no-label", codes(rep))


class LangTest(unittest.TestCase):
    def test_no_lang_trips_serious(self):
        rep = a11y_static.analyze('<html><body><main><h1>T</h1></main></body></html>')
        self.assertIn("html-no-lang", codes(rep))
        f = [x for x in rep["findings"] if x["code"] == "html-no-lang"][0]
        self.assertEqual(f["severity"], "serious")
        self.assertEqual(f["wcag"], "3.1.1")

    def test_empty_lang_trips(self):
        rep = a11y_static.analyze('<html lang=""><body><main><h1>T</h1></main></body></html>')
        self.assertIn("html-no-lang", codes(rep))


class ViewportTest(unittest.TestCase):
    def test_no_viewport_trips_serious(self):
        rep = a11y_static.analyze('<html lang="en"><head></head><body><main><h1>T</h1>'
                                  '</main></body></html>')
        self.assertIn("no-viewport-meta", codes(rep))

    def test_zoom_blocking_viewport_trips(self):
        rep = a11y_static.analyze('<html lang="en"><head>'
                                  '<meta name="viewport" content="width=device-width, user-scalable=no">'
                                  '</head><body><main><h1>T</h1></main></body></html>')
        self.assertIn("viewport-zoom-blocked", codes(rep))
        self.assertNotIn("no-viewport-meta", codes(rep))

    def test_maximum_scale_one_blocks_zoom(self):
        rep = a11y_static.analyze('<html lang="en"><head>'
                                  '<meta name="viewport" content="width=device-width, maximum-scale=1.0">'
                                  '</head><body><main><h1>T</h1></main></body></html>')
        self.assertIn("viewport-zoom-blocked", codes(rep))


class LandmarkAndSkipTest(unittest.TestCase):
    def test_no_main_landmark_is_moderate(self):
        rep = a11y_static.analyze('<html lang="en"><head>'
                                  '<meta name="viewport" content="width=device-width, initial-scale=1">'
                                  '</head><body><a href="#c">Skip</a><h1>T</h1></body></html>')
        self.assertIn("no-main-landmark", codes(rep))

    def test_role_main_counts_as_landmark(self):
        rep = a11y_static.analyze('<html lang="en"><head>'
                                  '<meta name="viewport" content="width=device-width, initial-scale=1">'
                                  '</head><body><a href="#c">Skip to content</a>'
                                  '<div role="main" id="c"><h1>T</h1></div></body></html>')
        self.assertNotIn("no-main-landmark", codes(rep))

    def test_no_skip_link_is_minor(self):
        rep = a11y_static.analyze('<html lang="en"><head>'
                                  '<meta name="viewport" content="width=device-width, initial-scale=1">'
                                  '</head><body><main><h1>T</h1></main></body></html>')
        self.assertIn("no-skip-link", codes(rep))
        f = [x for x in rep["findings"] if x["code"] == "no-skip-link"][0]
        self.assertEqual(f["severity"], "minor")

    def test_dead_skip_link_target_is_not_accepted(self):
        # FIX: a "skip" anchor whose href points at a NONEXISTENT id jumps nowhere, so the
        # page still has no working skip link (the finding is raised, not suppressed).
        rep = a11y_static.analyze('<html lang="en"><head>'
                                  '<meta name="viewport" content="width=device-width, initial-scale=1">'
                                  '</head><body><a href="#nowhere">Skip to content</a>'
                                  '<main id="main"><h1>T</h1></main></body></html>')
        self.assertIn("no-skip-link", codes(rep))

    def test_skip_link_to_real_id_passes(self):
        rep = a11y_static.analyze('<html lang="en"><head>'
                                  '<meta name="viewport" content="width=device-width, initial-scale=1">'
                                  '</head><body><a href="#main">Skip to content</a>'
                                  '<main id="main"><h1>T</h1></main></body></html>')
        self.assertNotIn("no-skip-link", codes(rep))


class TokenContrastTest(unittest.TestCase):
    def test_low_contrast_body_pair_trips_serious(self):
        # #777777 on #ffffff is ~4.48:1 -> below the 4.5 body minimum.
        tokens = {"colors": {"text": "#777777", "bg": "#ffffff",
                             "primary": "#0b5cad", "on_primary": "#ffffff"}}
        rep = a11y_static.analyze(CLEAN, tokens=tokens)
        cf = [x for x in rep["findings"] if x["code"] == "contrast-below-min"]
        self.assertTrue(cf, "expected a contrast finding for #777 on #fff")
        pairs = {f["pair"] for f in cf}
        self.assertIn("text/bg", pairs)

    def test_good_contrast_pair_passes(self):
        tokens = {"colors": {"text": "#111111", "bg": "#ffffff",
                             "primary": "#0b5cad", "on_primary": "#ffffff"}}
        rep = a11y_static.analyze(CLEAN, tokens=tokens)
        self.assertNotIn("contrast-below-min", codes(rep))

    def test_w3c_color_token_shape_supported(self):
        # tokens_emit.py --format json emits {"color": {"text": {"value": "#.."}}}
        tokens = {"color": {"text": {"value": "#999999"}, "bg": {"value": "#ffffff"}}}
        rep = a11y_static.analyze(CLEAN, tokens=tokens)
        self.assertIn("contrast-below-min", codes(rep))

    def test_no_tokens_means_no_contrast_check(self):
        rep = a11y_static.analyze(CLEAN)
        self.assertNotIn("contrast-below-min", codes(rep))


class RankingAndDeterminismTest(unittest.TestCase):
    def test_findings_sorted_by_severity(self):
        # a page with a critical (no label), serious (no alt), and minor (no skip link)
        html = ('<html lang="en"><head>'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '</head><body><main><h1>T</h1>'
                '<img src="x.jpg"><input type="text"></main></body></html>')
        rep = a11y_static.analyze(html)
        order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
        ranks = [order[f["severity"]] for f in rep["findings"]]
        self.assertEqual(ranks, sorted(ranks), "findings must be severity-ranked")
        self.assertEqual(rep["findings"][0]["severity"], "critical")

    def test_deterministic_output(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "p.html")
            with open(p, "w", encoding="utf-8") as f:
                f.write(CLEAN)
            a = run(["--file", p])[2]
            b = run(["--file", p])[2]
            self.assertEqual(a, b)


class HumanAsciiTest(unittest.TestCase):
    @staticmethod
    def _is_ascii(s):
        try:
            s.encode("ascii")
            return True
        except UnicodeEncodeError:
            return False

    def test_human_output_is_ascii(self):
        html = '<html><body><h1>T</h1><img src="x.jpg"></body></html>'
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "p.html")
            with open(p, "w", encoding="utf-8") as f:
                f.write(html)
            rc, _, out = run(["--file", p, "--human"])
            self.assertTrue(self._is_ascii(out), "human output must be pure ASCII")
            # findings present -> the checker still exits 0 (analysis succeeded)
            self.assertEqual(rc, 0)


class BadInputTest(unittest.TestCase):
    def test_no_input_errors_nonzero(self):
        rc, data, _ = run([])
        self.assertNotEqual(rc, 0)
        self.assertTrue(data is not None and data.get("error"))

    def test_missing_file_errors_nonzero(self):
        rc, data, _ = run(["--file", os.path.join(ROOT, "does-not-exist.html")])
        self.assertNotEqual(rc, 0)
        self.assertTrue(data is not None and data.get("error"))

    def test_bad_tokens_json_errors_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            hp = os.path.join(td, "p.html")
            tp = os.path.join(td, "t.json")
            with open(hp, "w", encoding="utf-8") as f:
                f.write(CLEAN)
            with open(tp, "w", encoding="utf-8") as f:
                f.write("{not valid json")
            rc, data, _ = run(["--file", hp, "--tokens", tp])
            self.assertNotEqual(rc, 0)
            self.assertTrue(data is not None and data.get("error"))

    def test_bad_flag_is_json_error_nonzero(self):
        rc, data, _ = run(["--nonsense"])
        self.assertNotEqual(rc, 0)
        self.assertTrue(data is not None and data.get("error"))

    def test_help_exits_zero(self):
        r = subprocess.run([sys.executable, A11Y, "-h"], capture_output=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
