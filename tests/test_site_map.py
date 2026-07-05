"""Tests for scripts/seo/site_map.py -- robots.txt + sitemap discovery + on-page
link harvest -> a classified URL inventory (free-first backbone, W1a).

Contract under test:
  * parse_sitemap / parse_robots / harvest_links / classify_page_type are pure,
    deterministic, offline functions;
  * the CLI runs fully OFFLINE via --file (+ --no-network), exits 0 on a good
    fixture, exits 1 with a JSON error object on bad input;
  * robots Disallow groups are respected (disallowed URLs flagged);
  * a sampled crawl states its sampling boundary;
  * the module wires the shared SSRF guard (validate_url import).

Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/`, no pip
install, no network (every case is a literal fixture or a --no-network CLI run).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "seo", "site_map.py")
sys.path.insert(0, os.path.join(ROOT, "scripts", "seo"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "workflow"))
import site_map  # noqa: E402


def _run(args):
    """Run the CLI offline. Returns (returncode, parsed_json_or_None, stdout)."""
    r = subprocess.run([sys.executable, SCRIPT] + args,
                       capture_output=True, text=True)
    parsed = None
    try:
        parsed = json.loads(r.stdout)
    except (ValueError, TypeError):
        parsed = None
    return r.returncode, parsed, r.stdout


SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://ex.com/</loc></url>
  <url><loc>https://ex.com/blog/post-1</loc></url>
  <url><loc>https://ex.com/product/widget</loc></url>
</urlset>
"""

SITEMAP_INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://ex.com/sitemap-1.xml</loc></sitemap>
  <sitemap><loc>https://ex.com/sitemap-2.xml</loc></sitemap>
</sitemapindex>
"""

HTML = """<!doctype html><html><head><title>t</title></head><body>
  <a href="/about">About</a>
  <a href="blog/post-2">Post 2</a>
  <a href="../contact">Contact</a>
  <a href="https://other.com/external">External</a>
  <a href="/private/secret">Secret</a>
  <a href="#frag">Frag only</a>
  <a href="mailto:a@b.com">Mail</a>
</body></html>
"""

ROBOTS = """User-agent: *
Disallow: /private/
Allow: /private/public-ok
Sitemap: https://ex.com/sitemap.xml
Sitemap: https://ex.com/news-sitemap.xml
"""


class PureFunctionTest(unittest.TestCase):
    def test_parse_sitemap_urlset(self):
        out = site_map.parse_sitemap(SITEMAP_XML)
        self.assertEqual(out["type"], "urlset")
        self.assertEqual(len(out["urls"]), 3)
        self.assertIn("https://ex.com/", out["urls"])

    def test_parse_sitemap_index(self):
        out = site_map.parse_sitemap(SITEMAP_INDEX_XML)
        self.assertEqual(out["type"], "sitemapindex")
        self.assertEqual(len(out["urls"]), 2)

    def test_parse_sitemap_bad_xml_raises(self):
        with self.assertRaises(ValueError):
            site_map.parse_sitemap("<<not xml")

    def test_classify_page_type(self):
        self.assertEqual(site_map.classify_page_type("https://ex.com/"), "home")
        self.assertEqual(site_map.classify_page_type("https://ex.com/blog/x"), "article")
        self.assertEqual(site_map.classify_page_type("https://ex.com/product/y"), "product")
        self.assertEqual(site_map.classify_page_type("https://ex.com/about"), "about")
        self.assertEqual(site_map.classify_page_type("https://ex.com/random/leaf"), "page")

    def test_harvest_links_resolves_and_filters(self):
        links = site_map.harvest_links(HTML, "https://ex.com/dir/page")
        self.assertIn("https://ex.com/about", links)
        self.assertIn("https://ex.com/dir/blog/post-2", links)
        self.assertIn("https://ex.com/contact", links)
        self.assertIn("https://other.com/external", links)
        # mailto and pure-fragment links are not http(s) page links
        self.assertFalse(any(l.startswith("mailto:") for l in links))
        self.assertFalse(any(l.endswith("#frag") for l in links))

    def test_is_internal(self):
        self.assertTrue(site_map.is_internal("https://ex.com/x", "https://www.ex.com/"))
        self.assertFalse(site_map.is_internal("https://other.com/x", "https://ex.com/"))

    def test_robots_disallow_respected(self):
        robots = site_map.parse_robots(ROBOTS)
        self.assertIn("https://ex.com/sitemap.xml", robots["sitemaps"])
        self.assertTrue(site_map.robots_disallows(robots, "/private/secret"))
        self.assertFalse(site_map.robots_disallows(robots, "/public/page"))
        # the more-specific Allow overrides the Disallow
        self.assertFalse(site_map.robots_disallows(robots, "/private/public-ok"))

    def test_sampling_note_exact_boundary(self):
        note = site_map.sampling_note(2, 5)
        self.assertIn("fetched 2 of 5", note)
        self.assertIn("Tier-1", note)

    def test_ssrf_guard_wired(self):
        # the shared SSRF guard must be importable from the module namespace.
        self.assertTrue(hasattr(site_map, "validate_url"))
        self.assertTrue(hasattr(site_map, "safe_open"))


class _FakeResp(object):
    def __init__(self, status, location=None, body=b"<html>ok</html>"):
        self.status = status
        self.headers = {"Location": location} if location else {}
        self._body = body

    def read(self, *a):
        return self._body

    def close(self):
        pass


class RedirectSsrfTest(unittest.TestCase):
    """FIX 3: site_map's fetch must refuse a redirect to an internal IP. OFFLINE: the
    start is a global literal IP (no DNS) and open_once is faked (no socket)."""

    def setUp(self):
        import net_safety
        self.net_safety = net_safety
        self._orig = net_safety.open_once

    def tearDown(self):
        self.net_safety.open_once = self._orig

    def test_fetch_refuses_redirect_to_metadata_ip(self):
        seq = {"http://8.8.8.8/": "http://169.254.169.254/latest/meta-data/"}
        self.net_safety.open_once = lambda url, **kw: _FakeResp(302, seq.get(url))
        with self.assertRaises(site_map.FetchError):
            site_map.fetch("http://8.8.8.8/")

    def test_fetch_refuses_redirect_to_loopback(self):
        seq = {"http://8.8.8.8/": "http://127.0.0.1/admin"}
        self.net_safety.open_once = lambda url, **kw: _FakeResp(302, seq.get(url))
        with self.assertRaises(site_map.FetchError):
            site_map.fetch("http://8.8.8.8/")


class CliOfflineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _write(self, name, text):
        p = os.path.join(self.tmp, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_offline_sitemap_file_exits_zero(self):
        p = self._write("sitemap.xml", SITEMAP_XML)
        code, js, _ = _run(["--file", p, "--no-network"])
        self.assertEqual(code, 0)
        self.assertIsNotNone(js)
        self.assertEqual(js["source_type"], "sitemap")
        self.assertEqual(js["counts"]["total"], 3)

    def test_offline_html_classifies_internal_external(self):
        p = self._write("page.html", HTML)
        code, js, _ = _run(["--file", p, "--base-url", "https://ex.com/", "--no-network"])
        self.assertEqual(code, 0)
        self.assertEqual(js["source_type"], "html")
        self.assertGreaterEqual(js["counts"]["external"], 1)
        self.assertGreaterEqual(js["counts"]["internal"], 1)

    def test_robots_disallow_flagged_in_inventory(self):
        hp = self._write("page.html", HTML)
        rp = self._write("robots.txt", ROBOTS)
        code, js, _ = _run(["--file", hp, "--base-url", "https://ex.com/",
                            "--robots-file", rp, "--no-network"])
        self.assertEqual(code, 0)
        disallowed = [it for it in js["inventory"] if it.get("disallowed")]
        self.assertTrue(any(it["url"].endswith("/private/secret") for it in disallowed))
        self.assertEqual(js["counts"]["disallowed"], len(disallowed))
        self.assertGreaterEqual(js["counts"]["disallowed"], 1)

    def test_sampled_mode_states_boundary(self):
        p = self._write("sitemap.xml", SITEMAP_XML)
        code, js, _ = _run(["--file", p, "--sample", "2", "--no-network"])
        self.assertEqual(code, 0)
        self.assertIn("sampling", js)
        self.assertIn("inventoried", js["sampling"])
        self.assertIn("Tier-1", js["sampling"]["note"])

    def test_human_output_ascii(self):
        p = self._write("sitemap.xml", SITEMAP_XML)
        r = subprocess.run([sys.executable, SCRIPT, "--file", p, "--no-network",
                            "--human"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, r.stdout.encode("ascii", "replace").decode("ascii"))
        self.assertIn("INVENTORY", r.stdout.upper())

    def test_bad_input_no_args_exits_nonzero_json(self):
        code, js, _ = _run([])
        self.assertNotEqual(code, 0)
        self.assertIsNotNone(js)
        self.assertIn("error", js)

    def test_bad_input_missing_file_exits_nonzero_json(self):
        code, js, _ = _run(["--file", os.path.join(self.tmp, "nope.xml"), "--no-network"])
        self.assertNotEqual(code, 0)
        self.assertIsNotNone(js)
        self.assertIn("error", js)


class EmptyInventoryExitTest(unittest.TestCase):
    """FIX 4: live discovery that produces NO inventory because every fetch failed or was
    SSRF-blocked must exit NON-ZERO with a JSON error -- warnings must not mask the
    failure. A successful offline --file parse still exits 0 with an inventory."""

    def test_all_fetches_blocked_exits_nonzero(self):
        import argparse
        orig = site_map.fetch

        def boom(u, timeout=10):
            raise site_map.FetchError("blocked url: simulated SSRF block")

        site_map.fetch = boom
        try:
            # http://8.8.8.8/ is a GLOBAL literal IP: validate_url(resolve=False) accepts
            # it offline, then every discovery fetch is the injected FetchError.
            args = argparse.Namespace(
                url="http://8.8.8.8/", file=None, robots_file=None,
                base_url=None, sample=None, no_network=False, human=False)
            report, code = site_map.run(args)
        finally:
            site_map.fetch = orig
        self.assertNotEqual(code, 0)
        self.assertTrue(report.get("errors"))
        self.assertEqual(report.get("inventory"), [])

    def test_offline_file_still_exits_zero_with_inventory(self):
        import argparse
        d = tempfile.mkdtemp()
        p = os.path.join(d, "sitemap.xml")
        with open(p, "w", encoding="utf-8") as f:
            f.write(SITEMAP_XML)
        args = argparse.Namespace(
            url=None, file=p, robots_file=None, base_url=None,
            sample=None, no_network=True, human=False)
        report, code = site_map.run(args)
        self.assertEqual(code, 0)
        self.assertTrue(report["inventory"])


if __name__ == "__main__":
    unittest.main()
