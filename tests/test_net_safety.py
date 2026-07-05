"""Tests for scripts/workflow/net_safety.py -- the shared SSRF guard every
URL-fetching script in the backbone imports.

Contract under test:
  validate_url(url, *, resolve=True, timeout=...) -> normalized URL str on ACCEPT;
  raises ValueError (UrlValidationError subclass) on REJECT.
  resolve=False validates the LITERAL host only (no DNS) -- the offline path.

Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/`, no pip
install, no network (every case is offline: literal IPs, userinfo, scheme, or
the literal-host accept path with resolve=False).
"""
import os
import socket
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "workflow"))
import net_safety  # noqa: E402
from net_safety import validate_url, UrlValidationError  # noqa: E402


class RejectTest(unittest.TestCase):
    """Every disallowed URL must raise -- offline-safe cases only."""

    def _assert_rejected(self, url, **kw):
        with self.assertRaises(ValueError, msg="should reject: %r" % url):
            validate_url(url, **kw)
        # UrlValidationError must be a ValueError subclass (callers may catch either).
        self.assertTrue(issubclass(UrlValidationError, ValueError))

    def test_loopback_ipv4_literal(self):
        # 127.0.0.1 is a literal IP -> checked without DNS even when resolve=True.
        self._assert_rejected("http://127.0.0.1")

    def test_cloud_metadata_ipv4(self):
        self._assert_rejected("http://169.254.169.254/latest/meta-data/")

    def test_cloud_metadata_ipv6(self):
        self._assert_rejected("http://[fd00:ec2::254]/latest/meta-data/")

    def test_loopback_ipv6_literal(self):
        self._assert_rejected("http://[::1]/")

    def test_userinfo_bypass(self):
        # user@host credential-injection / parser-confusion bypass.
        self._assert_rejected("http://user@evil.com/")

    def test_private_ipv4_literal(self):
        self._assert_rejected("http://10.0.0.5/")

    def test_nonhttp_scheme(self):
        self._assert_rejected("ftp://x")

    def test_localhost_name_literal_mode(self):
        # literal hostname 'localhost' must be blocked even with no DNS.
        self._assert_rejected("http://localhost", resolve=False)

    def test_localhost_name_resolve_mode(self):
        # and also when resolve=True (must not hit the network to decide).
        self._assert_rejected("http://localhost")

    def test_missing_host(self):
        self._assert_rejected("http://")

    def test_not_a_url(self):
        self._assert_rejected("not a url")

    def test_ipv4_mapped_ipv6_loopback(self):
        # ::ffff:127.0.0.1 must unwrap to the loopback v4 and be rejected.
        self._assert_rejected("http://[::ffff:127.0.0.1]/")

    # --- FIX 1: NAT64 / IPv4-mapped IPv6 embedding loopback -------------------
    def test_nat64_wellknown_prefix_loopback(self):
        # 64:ff9b::7f00:1 embeds 127.0.0.1 in the NAT64 well-known prefix /96.
        self._assert_rejected("http://[64:ff9b::7f00:1]/")

    def test_nat64_local_use_prefix_loopback(self):
        # 64:ff9b:1::7f00:1 embeds 127.0.0.1 in the NAT64 local-use /48.
        self._assert_rejected("http://[64:ff9b:1::7f00:1]/")

    # --- FIX 2: legacy IPv4 encodings (literal mode, resolve=False) -----------
    def test_decimal_ipv4_loopback(self):
        # 2130706433 == 127.0.0.1; must be rejected even with no DNS.
        self._assert_rejected("http://2130706433/", resolve=False)

    def test_hex_ipv4_loopback(self):
        self._assert_rejected("http://0x7f000001/", resolve=False)

    def test_dotted_hex_ipv4_loopback(self):
        self._assert_rejected("http://0x7f.0.0.1/", resolve=False)

    def test_octal_ipv4_loopback(self):
        self._assert_rejected("http://0177.0.0.1/", resolve=False)

    def test_octal_dwords_ipv4_loopback(self):
        self._assert_rejected("http://017700000001/", resolve=False)

    def test_dotted_short_ipv4_loopback(self):
        # 127.1 expands to 127.0.0.1.
        self._assert_rejected("http://127.1/", resolve=False)

    def test_decimal_ipv4_metadata(self):
        # 2852039166 == 169.254.169.254 (cloud metadata) in decimal.
        self._assert_rejected("http://2852039166/", resolve=False)

    # --- FIX 7: malformed port must REJECT, not silently drop ----------------
    def test_invalid_port_rejected(self):
        self._assert_rejected("http://example.com:bad/", resolve=False)

    # --- FIX 8: trailing-dot localhost / .localhost --------------------------
    def test_trailing_dot_localhost(self):
        self._assert_rejected("http://localhost./", resolve=False)

    def test_trailing_dot_sub_localhost(self):
        self._assert_rejected("http://x.localhost./", resolve=False)

    def test_dot_localhost_tld(self):
        self._assert_rejected("http://anything.localhost/", resolve=False)

    def test_trailing_dot_loopback_literal(self):
        self._assert_rejected("http://127.0.0.1./", resolve=False)


class AcceptTest(unittest.TestCase):
    def test_public_https_literal_mode(self):
        # resolve=False -> literal host only, no DNS; a normal public URL is accepted
        # and returned in normalized form.
        out = validate_url("https://example.com/", resolve=False)
        self.assertIsInstance(out, str)
        self.assertTrue(out.startswith("https://example.com"))

    def test_scheme_and_host_lowercased(self):
        out = validate_url("HTTPS://Example.COM/Path", resolve=False)
        self.assertTrue(out.startswith("https://example.com"))
        # path case is preserved
        self.assertIn("/Path", out)

    def test_deterministic(self):
        a = validate_url("https://example.com/a?b=1", resolve=False)
        b = validate_url("https://example.com/a?b=1", resolve=False)
        self.assertEqual(a, b)

    def test_trailing_dot_fqdn_accepted_and_canonicalized(self):
        # A single trailing FQDN dot on a normal public host is canonicalized away,
        # NOT rejected -- only localhost / literal-IP variants are blocked.
        out = validate_url("https://example.com./", resolve=False)
        self.assertTrue(out.startswith("https://example.com"))
        self.assertFalse(out.startswith("https://example.com."))

    def test_valid_port_preserved(self):
        out = validate_url("http://example.com:8080/x", resolve=False)
        self.assertIn(":8080", out)

    def test_global_decimal_ip_accepted(self):
        # 134744072 == 8.8.8.8 (global) -> a legacy encoding of a PUBLIC ip is allowed.
        out = validate_url("http://134744072/", resolve=False)
        self.assertIsInstance(out, str)


class _FakeResp(object):
    """Minimal stand-in for an http response object that safe_open consumes:
    a .status, a .headers mapping with .get/.items, a .read(), and a .close()."""

    def __init__(self, status, location=None, body=b"<html>ok</html>"):
        self.status = status
        self.headers = {"Location": location} if location else {}
        self._body = body
        self.closed = False

    def read(self, *a):
        return self._body

    def close(self):
        self.closed = True


class SafeOpenTest(unittest.TestCase):
    """The shared per-hop guarded fetch. Every case is OFFLINE: open_once is replaced
    with a fake so no socket is ever opened; resolve=False keeps validate_url off DNS."""

    def setUp(self):
        self._orig = net_safety.open_once

    def tearDown(self):
        net_safety.open_once = self._orig

    def _install(self, redirects):
        def fake(url, **kw):
            if url in redirects:
                return _FakeResp(302, location=redirects[url])
            return _FakeResp(200)
        net_safety.open_once = fake

    def test_blocks_redirect_to_internal_ip(self):
        # Every hop is re-validated: a redirect to a loopback IP is refused.
        self._install({"http://a.example/": "http://127.0.0.1/"})
        with self.assertRaises(UrlValidationError):
            net_safety.safe_open("http://a.example/", resolve=False)

    def test_blocks_redirect_to_metadata(self):
        self._install({"http://a.example/": "http://169.254.169.254/latest/"})
        with self.assertRaises(UrlValidationError):
            net_safety.safe_open("http://a.example/", resolve=False)

    def test_blocks_redirect_to_legacy_decimal_ip(self):
        # A redirect target encoded as a decimal loopback must also be refused.
        self._install({"http://a.example/": "http://2130706433/"})
        with self.assertRaises(UrlValidationError):
            net_safety.safe_open("http://a.example/", resolve=False)

    def test_detects_redirect_loop(self):
        self._install({"http://a.example/": "http://b.example/",
                       "http://b.example/": "http://a.example/"})
        with self.assertRaises(net_safety.RedirectLoopError):
            net_safety.safe_open("http://a.example/", resolve=False)

    def test_enforces_max_hops(self):
        chain = {"http://h%d.example/" % i: "http://h%d.example/" % (i + 1)
                 for i in range(10)}
        self._install(chain)
        with self.assertRaises(net_safety.MaxRedirectsError):
            net_safety.safe_open("http://h0.example/", resolve=False, max_hops=2)

    def test_blocked_start_url_never_fetches(self):
        # A disallowed start URL raises before open_once is ever called.
        net_safety.open_once = lambda *a, **k: self.fail("must not fetch a blocked URL")
        with self.assertRaises(UrlValidationError):
            net_safety.safe_open("http://127.0.0.1/", resolve=False)

    def test_success_returns_response_and_chain(self):
        self._install({"http://a.example/": "http://b.example/"})
        resp, chain = net_safety.safe_open("http://a.example/", resolve=False)
        self.assertEqual(resp.status, 200)
        self.assertEqual(chain[0]["url"], "http://a.example/")
        self.assertEqual(chain[-1]["url"], "http://b.example/")
        self.assertEqual(chain[0]["location"], "http://b.example/")


class PinnedFetchTest(unittest.TestCase):
    """FIX 1 (BLOCKER): the guarded fetch PINS to a validated IP, closing the
    DNS-rebinding TOCTOU. open_once / safe_open resolve the host ONCE, validate EVERY
    returned address, and connect to a CHECKED IP -- a host cannot resolve public for
    validate_url and private/metadata for the connection. Every case is offline:
    getaddrinfo is stubbed, or the pinned connection talks to a loopback test server."""

    def setUp(self):
        self._orig_gai = net_safety.socket.getaddrinfo

    def tearDown(self):
        net_safety.socket.getaddrinfo = self._orig_gai

    def _stub_gai(self, addr):
        net_safety.socket.getaddrinfo = (
            lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (addr, 0))])

    def test_resolve_validated_ips_blocks_private(self):
        # the host resolves to a metadata IP -> the authoritative resolution refuses it.
        self._stub_gai("169.254.169.254")
        with self.assertRaises(UrlValidationError):
            net_safety._resolve_validated_ips("rebind.example", 80, resolve=True)

    def test_resolve_validated_ips_returns_public_ip(self):
        self._stub_gai("93.184.216.34")
        out = net_safety._resolve_validated_ips("example.com", 80, resolve=True)
        self.assertTrue(any(ip == "93.184.216.34" for _fam, ip in out))

    def test_open_once_blocks_rebind_to_metadata(self):
        # getaddrinfo (re)resolves the name to a metadata IP at connect time: the pinned
        # fetch validates the resolved address and BLOCKS before opening any socket.
        self._stub_gai("169.254.169.254")
        with self.assertRaises(UrlValidationError):
            net_safety.open_once("http://rebind.example/", resolve=True)

    def test_safe_open_closes_dns_rebinding_toctou(self):
        # validate_url sees a PUBLIC address (call 1); the connect-time resolution inside
        # open_once returns a metadata address (call 2). The pin must catch the swap.
        public = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        meta = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 0))
        state = {"n": 0}

        def stub(*a, **k):
            state["n"] += 1
            return [public] if state["n"] == 1 else [meta]

        net_safety.socket.getaddrinfo = stub
        with self.assertRaises(UrlValidationError):
            net_safety.safe_open("http://rebind.example/", resolve=True)

    def test_pinned_connection_uses_checked_ip_and_original_host(self):
        # Stand up a loopback server; pin a connection whose ORIGINAL host is a public
        # name but whose validated IP is the loopback server. Prove the socket connects to
        # the PINNED ip while the Host header carries the ORIGINAL hostname.
        import http.server
        import threading
        captured = {}

        class _H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                captured["host"] = self.headers.get("Host")
                body = b"pinned-ok"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):  # silence the test server
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), _H)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.handle_request)
        t.daemon = True
        t.start()
        try:
            conn = net_safety._PinnedHTTPConnection(
                "example.com", "127.0.0.1", socket.AF_INET, port=port, timeout=5)
            conn.request("GET", "/")
            resp = conn.getresponse()
            data = resp.read()
            resp.close()
            conn.close()
        finally:
            t.join(timeout=5)
            srv.server_close()
        self.assertEqual(data, b"pinned-ok")
        self.assertTrue((captured.get("host") or "").startswith("example.com"),
                        "Host header must be the ORIGINAL host, got %r"
                        % captured.get("host"))


if __name__ == "__main__":
    unittest.main()
