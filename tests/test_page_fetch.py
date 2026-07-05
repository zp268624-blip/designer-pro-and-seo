"""Tests for scripts/seo/page_fetch.py -- the SSRF-guarded single-URL fetcher.

Contract under test:
  * follow_redirects() walks a redirect chain over an injected fetcher, validating
    EVERY hop through net_safety.validate_url (so a redirect to an internal IP is
    refused), caps hops, and detects redirect loops -- all provable OFFLINE with a
    fake fetcher (resolve=False keeps validate_url from touching DNS).
  * detect_spa_shell() is a pure heuristic over an HTML string.
  * CLI: `--file PATH` reads local HTML offline and exits 0; a missing file, a
    blocked URL (e.g. http://127.0.0.1), or `--url ... --no-network` with no file
    print a JSON error and exit non-zero. JSON by default; `--human` is ASCII.

Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/`, no pip
install, no network (every case is a literal-IP reject, a --file read, or a
fake-fetcher unit -- nothing ever leaves the process).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "seo", "page_fetch.py")
sys.path.insert(0, os.path.join(ROOT, "scripts", "seo"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "workflow"))
import net_safety  # noqa: E402
import page_fetch  # noqa: E402
from net_safety import UrlValidationError  # noqa: E402,F401


class _FakeResp(object):
    """Stand-in response for the net_safety.open_once seam (no socket opened). Exposes the
    .status / .headers / .read() / .close() shape safe_open + page_fetch consume."""

    def __init__(self, status, location=None, body=b"<html><body>ok</body></html>"):
        self.status = status
        self.headers = {"content-type": "text/html"}
        if location:
            self.headers["Location"] = location
        self._body = body

    def read(self, *a):
        return self._body

    def close(self):
        pass


class RoutedThroughSafeOpenTest(unittest.TestCase):
    """FIX 3 (MAJOR): page_fetch routes its fetch through net_safety.safe_open (the one
    per-hop-validating, IP-pinning fetch) instead of duplicating a redirect loop. OFFLINE:
    start hosts are GLOBAL literal IPs (validate_url accepts them with NO DNS) and
    net_safety.open_once is faked (no socket)."""

    def setUp(self):
        self._orig = net_safety.open_once

    def tearDown(self):
        net_safety.open_once = self._orig

    def _install(self, redirects=None, finals=None):
        redirects = redirects or {}
        finals = finals or {}

        def fake(url, **kw):
            if url in redirects:
                return _FakeResp(302, location=redirects[url])
            return _FakeResp(finals.get(url, 200))

        net_safety.open_once = fake

    def _call(self, url, **kw):
        kw.setdefault("head", False)
        kw.setdefault("detect_spa", False)
        kw.setdefault("max_hops", 10)
        kw.setdefault("timeout", 1.0)
        kw.setdefault("max_bytes", 10000)
        return page_fetch._result_from_url(url, **kw)

    def test_centralized_fetch_is_wired_no_local_loop(self):
        # the duplicated redirect machinery is gone; the shared fetch is imported.
        self.assertTrue(hasattr(page_fetch, "safe_open"))
        self.assertFalse(hasattr(page_fetch, "follow_redirects"))
        self.assertFalse(hasattr(page_fetch, "_http_fetch"))

    def test_simple_chain_ok(self):
        self._install(redirects={"http://8.8.8.8/": "http://1.1.1.1/"})
        code, result = self._call("http://8.8.8.8/")
        self.assertEqual(code, 0, result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["chain"][0]["url"], "http://8.8.8.8/")
        self.assertEqual(result["final_url"], "http://1.1.1.1/")
        self.assertEqual(result["redirects"], 1)

    def test_redirect_to_internal_ip_is_refused(self):
        self._install(redirects={"http://8.8.8.8/": "http://127.0.0.1/"})
        code, result = self._call("http://8.8.8.8/")
        self.assertNotEqual(code, 0)
        self.assertFalse(result["ok"])
        self.assertIn("SSRF", result["error"])
        self.assertIn("chain", result)

    def test_loop_detected(self):
        self._install(redirects={"http://8.8.8.8/": "http://1.1.1.1/",
                                 "http://1.1.1.1/": "http://8.8.8.8/"})
        code, result = self._call("http://8.8.8.8/")
        self.assertNotEqual(code, 0)
        self.assertIn("loop", result["error"])

    def test_max_hops_exceeded(self):
        ips = ["http://8.8.8.8/", "http://8.8.4.4/", "http://1.1.1.1/", "http://1.0.0.1/"]
        red = {ips[i]: ips[i + 1] for i in range(len(ips) - 1)}
        self._install(redirects=red)
        code, result = self._call(ips[0], max_hops=2)
        self.assertNotEqual(code, 0)
        self.assertIn("max-hops", result["error"])

    def test_transport_failure_returns_json_error_with_chain(self):
        def boom(url, **kw):
            raise urllib.error.URLError("boom")

        net_safety.open_once = boom
        code, result = self._call("http://8.8.8.8/")
        self.assertNotEqual(code, 0)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)
        self.assertIn("chain", result)        # the error path still reports a chain key


class SpaDetectTest(unittest.TestCase):
    def test_spa_shell_flagged(self):
        html = ('<html><head><title>x</title></head><body>'
                '<div id="root"></div><script src="/app.js"></script>'
                '</body></html>')
        res = page_fetch.detect_spa_shell(html)
        self.assertTrue(res["looks_like_spa"])

    def test_content_page_not_flagged(self):
        html = "<html><body><h1>Hello</h1><p>" + ("word " * 80) + "</p></body></html>"
        res = page_fetch.detect_spa_shell(html)
        self.assertFalse(res["looks_like_spa"])


class CliTest(unittest.TestCase):
    def _run(self, *args):
        p = subprocess.run([sys.executable, SCRIPT, *args],
                           capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr

    def test_file_offline_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "page.html")
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write("<html><body><h1>Hi</h1></body></html>")
            code, out, _ = self._run("--file", fp)
            self.assertEqual(code, 0, out)
            data = json.loads(out)
            self.assertTrue(data["ok"])
            self.assertGreater(data["bytes"], 0)

    def test_file_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "page.html")
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write("<html><body>same</body></html>")
            a = self._run("--file", fp)
            b = self._run("--file", fp)
            self.assertEqual(a[1], b[1])

    def test_missing_file_exits_nonzero(self):
        code, out, _ = self._run("--file", os.path.join(tempfile.gettempdir(),
                                                        "dps_no_such_file_zzz.html"))
        self.assertNotEqual(code, 0)
        data = json.loads(out)
        self.assertFalse(data["ok"])

    def test_blocked_url_refused_offline(self):
        # 127.0.0.1 is a literal IP -> validate_url rejects it before any network.
        code, out, _ = self._run("--url", "http://127.0.0.1/")
        self.assertNotEqual(code, 0)
        data = json.loads(out)
        self.assertFalse(data["ok"])

    def test_url_with_no_network_and_no_file_errors(self):
        code, out, _ = self._run("--url", "http://example.com/", "--no-network")
        self.assertNotEqual(code, 0)
        data = json.loads(out)
        self.assertFalse(data["ok"])

    def test_human_is_ascii(self):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "page.html")
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write("<html><body>cafe</body></html>")
            code, out, _ = self._run("--file", fp, "--human")
            self.assertEqual(code, 0, out)
            out.encode("ascii")  # raises if any non-ASCII leaked

    def test_detect_spa_offline_discloses_no_ua_swap(self):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "spa.html")
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write('<html><body><div id="root"></div>'
                         '<script src="/a.js"></script></body></html>')
            code, out, _ = self._run("--file", fp, "--detect-spa")
            self.assertEqual(code, 0, out)
            data = json.loads(out)
            self.assertIn("spa_detection", data)
            # offline: no second network fetch, so the UA-swap must be reported as
            # not performed (the contract is disclosure either way).
            self.assertFalse(data["spa_detection"]["ua_swap"]["performed"])

    def test_head_mode_omits_body_field(self):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "page.html")
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write("<html><body>body-here</body></html>")
            code, out, _ = self._run("--file", fp, "--head")
            self.assertEqual(code, 0, out)
            data = json.loads(out)
            self.assertNotIn("body", data)


if __name__ == "__main__":
    unittest.main()
