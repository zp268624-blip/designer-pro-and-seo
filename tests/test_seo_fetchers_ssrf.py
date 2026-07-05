"""FIX 4 -- the previously-unguarded SEO fetchers (tech_audit / geo_check /
drift_tools) must route their network access through the shared net_safety.safe_open,
so a blocked URL (internal/loopback/metadata/legacy-encoded IP) is refused before any
socket is opened.

Each module's fetch() returns an (..., error) tuple rather than raising, so the
contract under test is: a blocked URL yields NO body and a non-empty error, and the
shared guard is wired into the module namespace. Every case is OFFLINE: a literal
internal IP is rejected by validate_url with no DNS and no socket, and the redirect
cases fake net_safety.open_once.

Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/`, no pip install,
no network.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "seo"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "workflow"))
import net_safety  # noqa: E402
import tech_audit  # noqa: E402
import geo_check  # noqa: E402
import drift_tools  # noqa: E402


class _FakeResp(object):
    def __init__(self, status, location=None, body=b"<html>ok</html>"):
        self.status = status
        self.headers = {"Location": location} if location else {}
        self._body = body

    def read(self, *a):
        return self._body

    def close(self):
        pass


class GuardWiredTest(unittest.TestCase):
    def test_all_three_import_safe_open(self):
        for mod in (tech_audit, geo_check, drift_tools):
            self.assertTrue(hasattr(mod, "safe_open"),
                            "%s must import safe_open" % mod.__name__)


class BlockedLiteralTest(unittest.TestCase):
    """A literal internal IP is rejected by validate_url with no DNS / no socket."""

    def test_tech_audit_refuses_loopback(self):
        raw, headers, err = tech_audit.fetch("http://127.0.0.1/")
        self.assertIsNone(raw)
        self.assertTrue(err)

    def test_tech_audit_refuses_decimal_loopback(self):
        raw, headers, err = tech_audit.fetch("http://2130706433/")
        self.assertIsNone(raw)
        self.assertTrue(err)

    def test_geo_check_refuses_metadata(self):
        text, err = geo_check.fetch("http://169.254.169.254/latest/meta-data/")
        self.assertIsNone(text)
        self.assertTrue(err)

    def test_drift_tools_refuses_ipv6_loopback(self):
        text, err = drift_tools.fetch("http://[::1]/")
        self.assertIsNone(text)
        self.assertTrue(err)


class BlockedRedirectTest(unittest.TestCase):
    """A redirect to an internal IP must be refused per-hop. Start is a global literal
    IP (no DNS); open_once is faked (no socket)."""

    def setUp(self):
        self._orig = net_safety.open_once

    def tearDown(self):
        net_safety.open_once = self._orig

    def _fake(self, seq):
        net_safety.open_once = lambda url, **kw: _FakeResp(302, seq.get(url))

    def test_tech_audit_refuses_redirect_to_internal(self):
        self._fake({"http://8.8.8.8/": "http://10.0.0.5/"})
        raw, headers, err = tech_audit.fetch("http://8.8.8.8/")
        self.assertIsNone(raw)
        self.assertTrue(err)

    def test_geo_check_refuses_redirect_to_internal(self):
        self._fake({"http://8.8.8.8/": "http://169.254.169.254/"})
        text, err = geo_check.fetch("http://8.8.8.8/")
        self.assertIsNone(text)
        self.assertTrue(err)

    def test_drift_tools_refuses_redirect_to_internal(self):
        self._fake({"http://8.8.8.8/": "http://127.0.0.1/"})
        text, err = drift_tools.fetch("http://8.8.8.8/")
        self.assertIsNone(text)
        self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
