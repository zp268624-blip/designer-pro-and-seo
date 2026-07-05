#!/usr/bin/env python3
"""net_safety.py -- the one shared SSRF guard the whole free-first backbone imports.

Per ENGINE-CONTRACTS.md S15, *any* script that fetches a URL MUST import this
module and call `validate_url()` BEFORE fetching. SSRF protection is a contract,
not a per-script nicety -- there is no inline ad-hoc allowlist anywhere else.

Public API
----------
validate_url(url, *, resolve=True, timeout=5.0) -> str
    ACCEPT  -> returns a normalized URL string (scheme + host lowercased,
               userinfo dropped, IPv6 re-bracketed, path/query/fragment kept).
    REJECT  -> raises UrlValidationError (a subclass of ValueError) with a clear,
               ASCII, secret-free message. Callers may catch ValueError.

    A URL is REJECTED when:
      * its scheme is not http/https;
      * it has no host;
      * it carries a `user@host` userinfo segment (credential-injection /
        parser-confusion bypass);
      * the host is the literal name `localhost` (or a `*.localhost`);
      * the host is, or (when resolve=True) resolves to, an IP that is
        private / loopback / link-local / reserved / multicast / unspecified /
        non-global, the cloud-metadata address 169.254.169.254 or its IPv6 form
        fd00:ec2::254, or an IPv4-mapped/embedded form of any of those.

    resolve : when True (default) every address `socket.getaddrinfo` returns for
        the host is checked and the URL is rejected if ANY is disallowed -- this
        defeats DNS-rebinding to an internal IP. When False, DNS is skipped and
        only the literal host is validated (a literal IP host is still checked);
        this is the offline path used by unit tests and `--no-network`.

Output (CLI): JSON to stdout by default; `--human` prints an ASCII summary.
On a rejected/invalid URL the CLI prints a JSON error object and exits non-zero;
it never raises a raw traceback. ASCII-safe throughout.

Usage:
  py net_safety.py --url https://example.com/
  py net_safety.py --url http://169.254.169.254/ --json
  py net_safety.py --url https://example.com/ --no-network   # literal, no DNS
"""
import argparse
import http.client
import ipaddress
import json
import math
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse


class UrlValidationError(ValueError):
    """Raised when a URL is rejected by the SSRF guard. Subclasses ValueError so
    callers may catch either type."""


class SafeFetchError(Exception):
    """Base for redirect-handling failures inside safe_open (a redirect loop, or the
    hop cap being exceeded). Deliberately NOT a UrlValidationError: a blocked hop is a
    UrlValidationError (an SSRF refusal), whereas these are transport-shaped failures a
    caller may want to report differently."""


class RedirectLoopError(SafeFetchError):
    """A redirect pointed back to an already-visited URL."""


class MaxRedirectsError(SafeFetchError):
    """The redirect chain was still redirecting after the hop cap."""


# Shared fetch defaults reused by safe_open / open_once and by every script that
# routes its network access through this guard.
DEFAULT_UA = "Mozilla/5.0 (compatible; designer-pro-seo-netsafety/1.0; +stdlib)"
DEFAULT_MAX_HOPS = 5
DEFAULT_TIMEOUT = 10.0
REDIRECT_CODES = frozenset((301, 302, 303, 307, 308))


# Explicit cloud-metadata endpoints. 169.254.169.254 is also link-local and
# fd00:ec2::254 is also unique-local-private, so the generic flag checks below
# already block them; these are kept for an unambiguous, named rejection reason.
_METADATA_IPS = frozenset(
    ipaddress.ip_address(a) for a in ("169.254.169.254", "fd00:ec2::254")
)

# NAT64 translation prefixes (RFC 6052 well-known 64:ff9b::/96 and RFC 8215 local-use
# 64:ff9b:1::/48). An IPv6 address inside one of these embeds an IPv4 address an
# attacker controls (e.g. 127.0.0.1 -> 64:ff9b::7f00:1), so the embedded v4 is unwrapped
# and re-checked. (These prefixes are already flagged reserved/private by ipaddress, but
# the explicit unwrap is defense-in-depth that does not depend on that classification.)
_NAT64_PREFIXES = (
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("64:ff9b:1::/48"),
)


def _nat64_embedded(ip):
    """Return embedded-IPv4 candidates for an IPv6 address inside a NAT64 prefix, else
    an empty list. The low-32-bits reading covers both the standard `::7f00:1` form and
    the `::a.b.c.d` form for the well-known /96 and the local-use /48."""
    out = []
    try:
        if any(ip in net for net in _NAT64_PREFIXES):
            out.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    except (ValueError, TypeError):
        pass
    return out


def _ip_reason(ip):
    """Return an ASCII reason string if `ip` (an ipaddress object) is disallowed,
    else None. IPv4-mapped / 6to4 / Teredo / NAT64 IPv6 forms are unwrapped and the
    embedded IPv4 is checked too, so `::ffff:127.0.0.1` and `64:ff9b::7f00:1` cannot
    smuggle loopback past the v4 private/loopback/reserved checks."""
    if ip.version == 6:
        embedded = [
            getattr(ip, "ipv4_mapped", None),
            getattr(ip, "sixtofour", None),
            (ip.teredo[1] if getattr(ip, "teredo", None) else None),
        ]
        embedded.extend(_nat64_embedded(ip))
        for emb in embedded:
            if emb is not None:
                reason = _ip_reason(emb)
                if reason is not None:
                    return reason

    if ip in _METADATA_IPS:
        return "cloud-metadata address"
    if ip.is_unspecified:
        return "unspecified address"
    if ip.is_loopback:
        return "loopback address"
    if ip.is_link_local:
        return "link-local address"
    if ip.is_multicast:
        return "multicast address"
    if ip.is_reserved:
        return "reserved address"
    if ip.is_private:
        return "private address"
    if not ip.is_global:
        # Catches CGNAT (100.64/10), documentation ranges, and anything else not
        # publicly routable -- a strict block-list posture for an SSRF guard.
        return "non-global address"
    return None


def _parse_ip(host):
    """Return an ipaddress object if `host` is an IP literal, else None.
    Handles bare IPv6 (urlsplit already strips the [] brackets from hostname)."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _parse_int_token(tok):
    """Parse ONE inet_aton-style numeric component: `0x..` hex, leading-zero octal, or
    decimal. Returns a non-negative int, or None for an empty/malformed token. Mirrors
    the C resolver's per-part parsing without depending on the platform inet_aton."""
    if not tok:
        return None
    try:
        low = tok.lower()
        if low.startswith("0x"):
            return int(tok[2:], 16) if len(tok) > 2 else None
        if tok.startswith("0") and len(tok) > 1:
            return int(tok, 8)
        return int(tok, 10)
    except ValueError:
        return None


def _parse_legacy_ipv4(host):
    """Return a canonical IPv4Address for a NON-dotted-quad IPv4 literal the OS resolver
    would accept but `ipaddress` rejects -- decimal (2130706433), hex (0x7f000001 /
    0x7f.0.0.1), octal (017700000001 / 0177.0.0.1), and dotted-short (127.1) forms --
    else None. This closes the SSRF hole where such a literal would otherwise be treated
    as a domain name (and accepted under --no-network), then resolved to an internal IP
    by urllib. Canonical dotted-quads are handled by `_parse_ip`; a real hostname (which
    contains non-hex letters) parses to None here and falls through to the name path."""
    if not host or ":" in host:
        return None
    parts = host.split(".")
    if len(parts) > 4:
        return None
    nums = []
    for part in parts:
        n = _parse_int_token(part)
        if n is None or n < 0:
            return None
        nums.append(n)
    try:
        if len(parts) == 1:
            value = nums[0]
            limit = 0xFFFFFFFF
        elif len(parts) == 2:
            if nums[0] > 0xFF or nums[1] > 0xFFFFFF:
                return None
            value = (nums[0] << 24) | nums[1]
            limit = 0xFFFFFFFF
        elif len(parts) == 3:
            if nums[0] > 0xFF or nums[1] > 0xFF or nums[2] > 0xFFFF:
                return None
            value = (nums[0] << 24) | (nums[1] << 16) | nums[2]
            limit = 0xFFFFFFFF
        else:  # 4 parts -- a dotted quad whose parts used hex/octal encodings
            if any(n > 0xFF for n in nums):
                return None
            value = (nums[0] << 24) | (nums[1] << 16) | (nums[2] << 8) | nums[3]
            limit = 0xFFFFFFFF
        if value > limit:
            return None
        return ipaddress.IPv4Address(value)
    except (ValueError, ipaddress.AddressValueError):
        return None


def _normalize(scheme, host, parsed):
    """Rebuild a canonical URL: lowercased scheme + host, no userinfo, IPv6
    re-bracketed, original port/path/query/fragment preserved."""
    netloc = host
    if ":" in host and not host.startswith("["):
        netloc = "[" + host + "]"
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port is not None:
        netloc = "%s:%d" % (netloc, port)
    return urllib.parse.urlunsplit(
        (scheme, netloc, parsed.path or "", parsed.query, parsed.fragment)
    )


def validate_url(url, resolve=True, timeout=5.0):
    """Validate `url` against the SSRF contract. Return a normalized URL string
    on accept; raise UrlValidationError on reject. See module docstring."""
    if not isinstance(url, str) or not url.strip():
        raise UrlValidationError("empty or non-string url")

    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except ValueError as exc:
        raise UrlValidationError("unparseable url: %s" % exc)

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise UrlValidationError(
            "scheme not allowed: %r (only http/https)" % (parsed.scheme or "")
        )

    # A malformed port (e.g. 'http://example.com:bad/') only raises ValueError when
    # .port is accessed -- reject it here rather than silently dropping the port and
    # accepting a different URL than was requested.
    try:
        parsed.port
    except ValueError:
        raise UrlValidationError("invalid port in url authority")

    # Userinfo bypass: urlsplit exposes a username for `user@host`; also reject any
    # stray '@' in the authority that the parser did not surface as credentials.
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise UrlValidationError("userinfo (user@host) is not allowed")

    host = parsed.hostname  # lowercased, brackets stripped for IPv6, or None
    if not host:
        raise UrlValidationError("missing host")
    host = host.lower()

    # Canonicalize a single trailing FQDN dot so 'localhost.' / 'x.localhost.' / a
    # trailing-dot literal IP cannot dodge the name + IP checks below.
    if host.endswith(".") and len(host) > 1:
        host = host[:-1]

    # Literal-name block: localhost / *.localhost never resolve to anything safe,
    # and we must reject without depending on DNS.
    if host == "localhost" or host.endswith(".localhost"):
        raise UrlValidationError("host 'localhost' is not allowed")

    # If the host is itself an IP literal, check it directly -- no DNS needed,
    # regardless of the resolve flag (a literal internal IP is always blocked).
    literal_ip = _parse_ip(host)
    if literal_ip is not None:
        reason = _ip_reason(literal_ip)
        if reason is not None:
            raise UrlValidationError("disallowed host %s: %s" % (host, reason))
        return _normalize(scheme, host, parsed)

    # A non-dotted-quad IPv4 literal (decimal/hex/octal/dotted-short) is invisible to
    # `ipaddress` but the OS resolver expands it -- normalize and disallow-check it here,
    # even offline, before we ever treat the host as a domain name.
    legacy_ip = _parse_legacy_ipv4(host)
    if legacy_ip is not None:
        reason = _ip_reason(legacy_ip)
        if reason is not None:
            raise UrlValidationError(
                "disallowed host %s (%s): %s" % (host, legacy_ip, reason))
        return _normalize(scheme, host, parsed)

    # Hostname. In literal mode we cannot resolve; accept the (non-localhost) name
    # after the structural checks above. In resolve mode, block if ANY resolved
    # address is disallowed (DNS-rebinding defense).
    if resolve:
        try:
            infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise UrlValidationError("could not resolve host %s: %s" % (host, exc))
        except OSError as exc:
            raise UrlValidationError("host resolution failed for %s: %s" % (host, exc))
        if not infos:
            raise UrlValidationError("host %s resolved to no addresses" % host)
        for info in infos:
            sockaddr = info[4]
            addr = sockaddr[0]
            # Strip any IPv6 scope id (e.g. "fe80::1%eth0").
            addr = addr.split("%", 1)[0]
            ip = _parse_ip(addr)
            if ip is None:
                raise UrlValidationError(
                    "host %s resolved to unparseable address" % host
                )
            reason = _ip_reason(ip)
            if reason is not None:
                raise UrlValidationError(
                    "host %s resolves to a disallowed address (%s)" % (host, reason)
                )

    return _normalize(scheme, host, parsed)


def _default_port(scheme):
    return 443 if scheme == "https" else 80


def _resolve_validated_ips(host, port, *, resolve=True):
    """Resolve `host` to IPs ONCE and validate EVERY returned address, returning a list of
    (family, ip_str) for the addresses that passed -- the AUTHORITATIVE resolution the
    pinned connection then connects to. Resolving here (rather than letting the transport
    re-resolve at connect time) is what closes the DNS-rebinding TOCTOU: the IP we connect
    to is one we just validated.

      * a literal-IP host (dotted-quad / IPv6 / a legacy decimal/hex/octal encoding) is
        validated directly, with NO DNS, regardless of `resolve`;
      * with resolve=True a name is resolved via socket.getaddrinfo and EVERY address is
        checked (block if ANY is disallowed);
      * with resolve=False a NON-literal host raises -- the offline/--no-network path never
        opens a socket to a name, so it must not silently re-resolve outside the guard.

    Raises UrlValidationError if ANY address is disallowed, the name cannot be resolved, or
    a name is asked for under resolve=False."""
    literal = _parse_ip(host)
    if literal is None:
        literal = _parse_legacy_ipv4(host)
    if literal is not None:
        reason = _ip_reason(literal)
        if reason is not None:
            raise UrlValidationError("disallowed host %s: %s" % (host, reason))
        family = socket.AF_INET6 if literal.version == 6 else socket.AF_INET
        return [(family, str(literal))]
    if not resolve:
        raise UrlValidationError(
            "cannot pin host %s without DNS (offline/--no-network)" % host)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlValidationError("could not resolve host %s: %s" % (host, exc))
    except OSError as exc:
        raise UrlValidationError("host resolution failed for %s: %s" % (host, exc))
    out, seen = [], set()
    for info in infos:
        family = info[0]
        addr = info[4][0].split("%", 1)[0]  # strip any IPv6 scope id (fe80::1%eth0)
        ip = _parse_ip(addr)
        if ip is None:
            raise UrlValidationError("host %s resolved to unparseable address" % host)
        reason = _ip_reason(ip)
        if reason is not None:
            raise UrlValidationError(
                "host %s resolves to a disallowed address (%s)" % (host, reason))
        key = (family, str(ip))
        if key not in seen:
            seen.add(key)
            out.append((family, str(ip)))
    if not out:
        raise UrlValidationError("host %s resolved to no addresses" % host)
    return out


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """An HTTPConnection that connects to a PRE-VALIDATED ip instead of re-resolving
    self.host at connect time. The request's Host header still derives from self.host (the
    ORIGINAL hostname), so correctness is preserved while the socket is pinned to the
    checked address -- the core DNS-rebinding TOCTOU defense."""

    def __init__(self, host, ip, family, **kwargs):
        super().__init__(host, **kwargs)
        self._pinned_ip = ip
        self._pinned_family = family

    def connect(self):
        self.sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self._tunnel()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS variant: connects to the validated ip, then wraps TLS with the ORIGINAL
    hostname as SNI + certificate-check name (ssl.create_default_context verifies the cert
    against self.host, NOT the bare IP) -- so pinning never weakens TLS identity."""

    def __init__(self, host, ip, family, *, context=None, **kwargs):
        if context is None:
            context = ssl.create_default_context()
        super().__init__(host, context=context, **kwargs)
        self._pinned_ip = ip
        self._pinned_family = family

    def connect(self):
        sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
            sock = self.sock
        server_hostname = self._tunnel_host or self.host
        self.sock = self._context.wrap_socket(sock, server_hostname=server_hostname)


def _bind_conn_close(resp, conn):
    """Make closing the response also close the pinned connection's socket (we open one
    connection per request, no pooling), so a caller's existing `resp.close()` cleans up
    everything and no socket is leaked."""
    orig_close = resp.close

    def _close():
        try:
            orig_close()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    resp.close = _close


def open_once(url, *, method="GET", headers=None, timeout=DEFAULT_TIMEOUT, resolve=True):
    """Issue exactly ONE HTTP/HTTPS request with NO automatic redirect following, PINNED to
    a validated IP, and return the response object (an http.client.HTTPResponse exposing
    .status/.headers/.read()/.close()). The CALLER must read and close it.

    This is the single shared transport primitive. The host is resolved ONCE here, EVERY
    resolved address is validated, and the socket connects to a CHECKED IP -- so a host
    cannot resolve public for validate_url and private/metadata for the connection
    (DNS-rebinding TOCTOU). The Host header (and, for TLS, SNI + cert name) stays the
    ORIGINAL hostname so the request remains correct.

    Raises UrlValidationError if the resolved/literal address is disallowed; transport and
    protocol failures surface as urllib.error.URLError / OSError / TimeoutError (the
    exception types every caller already handles)."""
    headers = headers or {"User-Agent": DEFAULT_UA}
    parsed = urllib.parse.urlsplit(url)
    scheme = (parsed.scheme or "").lower()
    host = parsed.hostname
    if not host:
        raise UrlValidationError("missing host")
    host = host.lower()
    try:
        port = parsed.port or _default_port(scheme)
    except ValueError:
        raise UrlValidationError("invalid port in url authority")

    family, ip = _resolve_validated_ips(host, port, resolve=resolve)[0]

    path = parsed.path or "/"
    if parsed.query:
        path = path + "?" + parsed.query

    if scheme == "https":
        conn = _PinnedHTTPSConnection(host, ip, family, port=port, timeout=timeout)
    else:
        conn = _PinnedHTTPConnection(host, ip, family, port=port, timeout=timeout)
    try:
        conn.request(method, path, headers=headers)
        resp = conn.getresponse()
    except http.client.HTTPException as exc:
        try:
            conn.close()
        except Exception:
            pass
        # normalize protocol errors to URLError so callers' existing except clauses catch.
        raise urllib.error.URLError(exc)
    except BaseException:
        try:
            conn.close()
        except Exception:
            pass
        raise
    _bind_conn_close(resp, conn)
    return resp


def safe_open(url, *, method="GET", headers=None, max_hops=DEFAULT_MAX_HOPS,
              timeout=DEFAULT_TIMEOUT, resolve=True):
    """The one shared per-hop SSRF-guarded fetch the whole plugin reuses.

    Validates the START url, then follows each redirect MANUALLY -- re-validating every
    hop's Location through validate_url BEFORE fetching it -- with a hop cap and loop
    detection. EACH hop is fetched via open_once, which resolves the host ONCE, validates
    every resolved address, and PINS the socket to a checked IP -- so every hop's actual
    connection lands on a validated address (no urllib re-resolution, no DNS-rebinding).
    Returns (response, chain): `response` is the final non-redirect response object (the
    caller reads + closes it); `chain` is the validated hop list
    [{"url", "status", "location"?}, ...].

    Raises:
      UrlValidationError  -- the start URL or ANY redirect hop is disallowed (SSRF), incl.
                             a connect-time rebind caught by open_once's pin;
      RedirectLoopError   -- a hop points back to an already-visited URL;
      MaxRedirectsError   -- still redirecting after `max_hops` hops.
    Each raised exception carries a `.chain` attribute (the validated hops so far) so a
    caller can report the partial chain. Transport failures (URLError/OSError/TimeoutError)
    propagate to the caller."""
    if headers is None:
        headers = {"User-Agent": DEFAULT_UA}
    chain = []
    visited = []
    current = url
    for _ in range(max_hops + 1):
        try:
            norm = validate_url(current, resolve=resolve)  # raises on a blocked hop
        except UrlValidationError as exc:
            exc.chain = list(chain)
            raise
        if norm in visited:
            chain.append({"url": norm, "loop": True})
            err = RedirectLoopError("redirect loop detected at %s" % norm)
            err.chain = list(chain)
            raise err
        visited.append(norm)
        try:
            resp = open_once(norm, method=method, headers=headers, timeout=timeout,
                             resolve=resolve)
        except UrlValidationError as exc:
            # the pinned connect-time resolution caught a disallowed/rebound address.
            exc.chain = list(chain)
            raise
        status = getattr(resp, "status", None)
        if status is None:
            status = getattr(resp, "code", None)
        location = None
        resp_headers = getattr(resp, "headers", None)
        if resp_headers is not None:
            location = resp_headers.get("Location")
        entry = {"url": norm, "status": status}
        if status in REDIRECT_CODES and location:
            nxt = urllib.parse.urljoin(norm, location)
            entry["location"] = nxt
            chain.append(entry)
            try:
                resp.close()
            except Exception:
                pass
            current = nxt
            continue
        chain.append(entry)
        return resp, chain
    err = MaxRedirectsError("redirect chain exceeded max-hops (%d)" % max_hops)
    err.chain = list(chain)
    raise err


def _build_result(url, resolve):
    try:
        normalized = validate_url(url, resolve=resolve)
        return 0, {"ok": True, "url": url, "normalized": normalized,
                   "resolved": resolve}
    except UrlValidationError as exc:
        return 2, {"ok": False, "url": url, "error": str(exc)}


def _format_human(result):
    if result.get("ok"):
        lines = ["URL: ALLOWED", "  input      : " + str(result["url"]),
                 "  normalized : " + str(result["normalized"]),
                 "  dns-checked: " + ("yes" if result.get("resolved") else "no")]
    else:
        lines = ["URL: REJECTED", "  input : " + str(result["url"]),
                 "  reason: " + str(result["error"])]
    text = "\n".join(lines)
    return text.encode("ascii", "replace").decode("ascii")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate a URL against the shared SSRF guard."
    )
    parser.add_argument("--url", required=True, help="the URL to validate")
    parser.add_argument("--json", action="store_true",
                        help="force JSON output (the default)")
    parser.add_argument("--human", action="store_true",
                        help="ASCII summary instead of JSON")
    parser.add_argument("--no-network", action="store_true",
                        help="validate the literal host only; skip DNS resolution")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        # argparse already printed a usage error to stderr and set a non-zero code.
        raise

    code, result = _build_result(args.url, resolve=not args.no_network)
    if args.human and not args.json:
        print(_format_human(result))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
