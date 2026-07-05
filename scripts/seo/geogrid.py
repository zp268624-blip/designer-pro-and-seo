#!/usr/bin/env python3
"""
geogrid.py -- Share-of-Local-Voice (SoLV) geo-grid math + a center+radius grid
builder for local-maps rank tracking (seo-local-unified flagship, Wave 3a).

Two modes, one script:

  SoLV (default, `--grid FILE`): given a grid of lat/lng points each carrying the
  business's local-pack rank at that point, compute the Share of Local Voice and the
  supporting coverage metrics. Pure math over SUPPLIED rank data -- it never fetches
  live SERP ranks (those are a Tier-1 acquisition step), so it is fully offline,
  deterministic, and golden-file testable.

  Build-grid (`--build-grid`): generate an N x N grid of coordinates around a center
  (`--center "lat,lng"`) or a geocoded address (`--geocode "address"`), spaced by a
  radius in km, with every point un-ranked -- the scaffold the caller fills with rank
  data (from a maps connector or manual checks) and feeds back into SoLV mode.

SoLV formula (authored from first principles; see references/seo-local-unified/solv-geogrid-formula.md):
  Per point i with rank r_i (1-based), within scan depth D, per-point visibility is the
  reciprocal rank  v_i = 1 / r_i  (v=1.0 at rank 1, decaying with rank); a point where
  the business is not found within D contributes v_i = 0. With optional per-point
  weights w_i (default 1.0),
        SoLV% = 100 * ( sum_i w_i * v_i ) / ( sum_i w_i ) .
  Reported alongside: coverage% (found / total), top3% (rank <= 3 / total), the average
  found rank, and the best/worst found rank. No metric is fabricated -- a never-found
  grid scores 0, honestly.

SSRF: only `--geocode` touches the network, and it routes through the one shared guard
(`scripts/workflow/net_safety.safe_open`) -- never urlopen directly. `--center`,
`--grid`, and `--no-network` never fetch.

Output: JSON to stdout by default; `--human` prints an ASCII summary. Bad input
(missing/unreadable/unparseable file, empty grid, non-numeric coord/rank, no center
for build mode, geocode under --no-network) prints a JSON error object and exits
non-zero -- never a raw traceback. ASCII-safe throughout. Standard library only;
deterministic.

Usage:
  py geogrid.py --grid grid.json
  py geogrid.py --grid grid.json --depth 20 --human
  py geogrid.py --build-grid --center "40.23,-111.66" --radius 2 --size 5
  py geogrid.py --build-grid --geocode "Provo, UT" --radius 3 --size 7
"""
import argparse
import json
import math
import os
import sys
import urllib.parse

# net_safety lives in the sibling scripts/workflow/ dir; bootstrap sys.path so the one
# shared SSRF guard imports cleanly. EVERY network fetch (only --geocode here) routes
# through safe_open -- never urllib.urlopen directly.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "workflow"))
from net_safety import (  # noqa: E402
    safe_open, UrlValidationError, RedirectLoopError, MaxRedirectsError,
)
import urllib.error  # noqa: E402

DEFAULT_DEPTH = 20
DEFAULT_RADIUS_KM = 2.0
DEFAULT_SIZE = 5
KM_PER_DEG_LAT = 111.32  # mean km per degree of latitude (WGS84 approximation)
NOMINATIM_UA = "Mozilla/5.0 (compatible; designer-pro-seo-geogrid/1.0; +stdlib)"


class InputError(Exception):
    """Bad caller input -> a JSON error object + non-zero exit (never a traceback)."""


class _JsonArgParser(argparse.ArgumentParser):
    """argparse's own failures (a missing required arg, a bad type/choice) must honor the
    JSON-error contract too: emit {"error": ...} to stdout + a non-zero exit, never a bare
    usage dump to stderr. stdlib + ASCII."""
    def error(self, message):
        msg = str(message).encode("ascii", "replace").decode("ascii")
        print(json.dumps({"error": msg}))
        sys.exit(2)


def _num(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError("%s must be a number, got %r" % (label, value))
    if math.isnan(value) or math.isinf(value):
        raise InputError("%s must be finite" % label)
    return float(value)


def _rank(value):
    """Return a positive int rank, or None for not-found (null / 0 / absent). A
    non-integer, negative, or otherwise malformed rank is a hard input error."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise InputError("rank must be an integer or null, got %r" % value)
    if isinstance(value, float):
        if not value.is_integer():
            raise InputError("rank must be a whole number, got %r" % value)
        value = int(value)
    if not isinstance(value, int):
        raise InputError("rank must be an integer or null, got %r" % value)
    if value < 0:
        raise InputError("rank must be >= 0 (0/null = not found), got %r" % value)
    return None if value == 0 else value


def _round(x, places=2):
    return round(x + 0.0, places)


def compute_solv(grid, depth_override=None):
    """Core SoLV math over a parsed grid dict. Returns the result dict. Raises
    InputError on a malformed grid. Pure + deterministic (input point order preserved)."""
    if not isinstance(grid, dict):
        if isinstance(grid, list):
            grid = {"points": grid}
        else:
            raise InputError("grid must be a JSON object or a list of points")
    points = grid.get("points")
    if not isinstance(points, list) or not points:
        raise InputError("grid has no points (expected a non-empty 'points' list)")

    depth = depth_override if depth_override is not None else grid.get("depth", DEFAULT_DEPTH)
    depth = int(_num(depth, "depth"))
    if depth < 1:
        raise InputError("depth must be >= 1")

    out_points = []
    found_ranks = []
    num = 0.0  # sum(w_i * v_i)
    den = 0.0  # sum(w_i)
    top3 = 0
    weighted = False
    for idx, pt in enumerate(points):
        if not isinstance(pt, dict):
            raise InputError("point %d is not an object" % idx)
        lat = _num(pt.get("lat"), "point %d lat" % idx)
        lng = _num(pt.get("lng"), "point %d lng" % idx)
        rank = _rank(pt.get("rank"))
        weight = _num(pt.get("weight", 1.0), "point %d weight" % idx)
        if weight < 0:
            raise InputError("point %d weight must be >= 0" % idx)
        if weight != 1.0:
            weighted = True
        found = rank is not None and rank <= depth
        visibility = (1.0 / rank) if found else 0.0
        if found:
            found_ranks.append(rank)
            if rank <= 3:
                top3 += 1
        num += weight * visibility
        den += weight
        out_points.append({
            "lat": lat, "lng": lng, "rank": rank if found else None,
            "found": found, "visibility": _round(visibility, 6), "weight": weight,
        })

    if den <= 0:
        raise InputError("total point weight is zero -- cannot compute SoLV")

    n = len(out_points)
    found_n = len(found_ranks)
    return {
        "ok": True,
        "mode": "solv",
        "business": grid.get("business"),
        "keyword": grid.get("keyword"),
        "depth": depth,
        "grid_points": n,
        "found_points": found_n,
        "solv_percent": _round(100.0 * num / den, 2),
        "coverage_percent": _round(100.0 * found_n / n, 2),
        "top3_percent": _round(100.0 * top3 / n, 2),
        "avg_rank_found": _round(sum(found_ranks) / found_n, 2) if found_n else None,
        "best_rank": min(found_ranks) if found_ranks else None,
        "worst_rank": max(found_ranks) if found_ranks else None,
        "weighted": weighted,
        "points": out_points,
    }


def _parse_center(text):
    """Parse a "lat,lng" string into (lat, lng) floats, or raise InputError."""
    if not isinstance(text, str) or "," not in text:
        raise InputError("--center must be \"lat,lng\" (e.g. 40.23,-111.66)")
    a, b = text.split(",", 1)
    try:
        lat = float(a.strip())
        lng = float(b.strip())
    except ValueError:
        raise InputError("--center must be two numbers \"lat,lng\"")
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        raise InputError("--center out of range (lat -90..90, lng -180..180)")
    return lat, lng


def _geocode(address, *, resolve=True, timeout=10.0):
    """Resolve an address to (lat, lng, display_name) via the free OpenStreetMap
    Nominatim service -- fetched ONLY through the shared SSRF guard (safe_open).
    Raises InputError on any failure so the CLI degrades to a JSON error, never a hang."""
    q = urllib.parse.urlencode({"q": address, "format": "json", "limit": "1"})
    url = "https://nominatim.openstreetmap.org/search?" + q
    try:
        resp, _chain = safe_open(url, headers={"User-Agent": NOMINATIM_UA},
                                 timeout=timeout, resolve=resolve)
        try:
            body = resp.read(1_000_000) or b""
        finally:
            try:
                resp.close()
            except Exception:
                pass
    except (UrlValidationError, RedirectLoopError, MaxRedirectsError,
            urllib.error.URLError, OSError, TimeoutError) as exc:
        raise InputError("geocode fetch failed: %s" % exc)
    try:
        data = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        raise InputError("geocode response was not valid JSON")
    if not isinstance(data, list) or not data:
        raise InputError("geocode found no match for %r" % address)
    top = data[0]
    try:
        return float(top["lat"]), float(top["lon"]), top.get("display_name")
    except (KeyError, ValueError, TypeError):
        raise InputError("geocode response missing lat/lon")


def build_grid(lat0, lng0, radius_km, size, *, center_label=None):
    """Build an `size` x `size` grid of coordinates centered on (lat0, lng0), spanning
    +/- radius_km on each axis. Deterministic. Rows run north->south, columns west->east;
    every point is un-ranked (rank=None) so the caller can fill it in."""
    if size < 1:
        raise InputError("--size must be >= 1")
    if radius_km < 0:
        raise InputError("--radius must be >= 0")
    step_km = (2.0 * radius_km) / (size - 1) if size > 1 else 0.0
    dlat_per_km = 1.0 / KM_PER_DEG_LAT
    coslat = math.cos(math.radians(lat0))
    # Guard the pole singularity: clamp the longitude scale so we never divide by ~0.
    dlng_per_km = 1.0 / (KM_PER_DEG_LAT * coslat) if abs(coslat) > 1e-9 else 0.0
    points = []
    for i in range(size):
        north_km = radius_km - i * step_km
        for j in range(size):
            east_km = -radius_km + j * step_km
            lat = round(lat0 + north_km * dlat_per_km, 6)
            lng = round(lng0 + east_km * dlng_per_km, 6)
            points.append({"lat": lat, "lng": lng, "rank": None})
    return {
        "ok": True,
        "mode": "build-grid",
        "center": {"lat": lat0, "lng": lng0, "label": center_label},
        "radius_km": float(radius_km),
        "size": size,
        "step_km": _round(step_km, 6),
        "grid_points": len(points),
        "points": points,
    }


def _load_grid_file(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise InputError("could not read grid file: %s" % exc)
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise InputError("grid file is not valid JSON: %s" % exc)


def build_result(args):
    """Return (exit_code, result_dict). No printing here. All input errors degrade to a
    JSON {"ok": false, "error": ...} object + a non-zero exit."""
    try:
        if args.build_grid:
            if args.geocode:
                if args.no_network:
                    raise InputError(
                        "--geocode needs the network; --no-network forbids it "
                        "(use --center \"lat,lng\" offline)")
                lat0, lng0, label = _geocode(args.geocode, resolve=True,
                                             timeout=args.timeout)
            elif args.center:
                lat0, lng0 = _parse_center(args.center)
                label = None
            else:
                raise InputError("--build-grid needs --center \"lat,lng\" or --geocode \"address\"")
            return 0, build_grid(lat0, lng0, args.radius, args.size, center_label=label)

        if not args.grid:
            raise InputError("no input: pass --grid FILE (SoLV) or --build-grid")
        grid = _load_grid_file(args.grid)
        return 0, compute_solv(grid, depth_override=args.depth)
    except InputError as exc:
        return 2, {"ok": False, "error": str(exc)}


def _format_human(r):
    lines = []
    if not r.get("ok"):
        lines.append("GEOGRID: ERROR")
        lines.append("  error: %s" % r.get("error"))
        return "\n".join(lines).encode("ascii", "replace").decode("ascii")
    if r.get("mode") == "build-grid":
        c = r.get("center", {})
        lines.append("GEOGRID: built %dx%d grid (%d points)"
                     % (r["size"], r["size"], r["grid_points"]))
        lines.append("  center : %s, %s%s"
                     % (c.get("lat"), c.get("lng"),
                        (" (%s)" % c["label"]) if c.get("label") else ""))
        lines.append("  radius : %s km   step: %s km" % (r["radius_km"], r["step_km"]))
        lines.append("  (every point un-ranked -- fill rank then re-run --grid for SoLV)")
    else:
        lines.append("GEOGRID: Share of Local Voice")
        if r.get("business"):
            lines.append("  business : %s" % r["business"])
        if r.get("keyword"):
            lines.append("  keyword  : %s" % r["keyword"])
        lines.append("  SoLV          : %.2f%%" % r["solv_percent"])
        lines.append("  coverage      : %.2f%% (%d/%d points found)"
                     % (r["coverage_percent"], r["found_points"], r["grid_points"]))
        lines.append("  top-3 share   : %.2f%%" % r["top3_percent"])
        avg = r.get("avg_rank_found")
        lines.append("  avg found rank: %s   best: %s   worst: %s"
                     % (avg, r.get("best_rank"), r.get("worst_rank")))
        lines.append("  weighted      : %s   depth: %s" % (r["weighted"], r["depth"]))
    return "\n".join(lines).encode("ascii", "replace").decode("ascii")


def main(argv=None):
    ap = _JsonArgParser(
        description="Share-of-Local-Voice (SoLV) geo-grid math + grid builder.")
    ap.add_argument("--grid", help="JSON grid file with per-point rank data (SoLV mode)")
    ap.add_argument("--build-grid", action="store_true",
                    help="build an N x N coordinate grid around a center")
    ap.add_argument("--center", help="grid center as \"lat,lng\" (build mode, offline)")
    ap.add_argument("--geocode", help="geocode this address for the center (needs network)")
    ap.add_argument("--radius", type=float, default=DEFAULT_RADIUS_KM,
                    help="half-extent of the grid in km (default %.1f)" % DEFAULT_RADIUS_KM)
    ap.add_argument("--size", type=int, default=DEFAULT_SIZE,
                    help="grid is size x size points (default %d)" % DEFAULT_SIZE)
    ap.add_argument("--depth", type=int, default=None,
                    help="rank scan depth; ranks beyond this count as not-found "
                         "(default %d or the grid file's value)" % DEFAULT_DEPTH)
    ap.add_argument("--timeout", type=float, default=10.0,
                    help="geocode request timeout seconds (default 10)")
    ap.add_argument("--no-network", action="store_true",
                    help="forbid any network fetch (geocode then errors)")
    ap.add_argument("--json", action="store_true", help="force JSON (the default)")
    ap.add_argument("--human", action="store_true", help="ASCII summary instead of JSON")
    args = ap.parse_args(argv)

    code, result = build_result(args)
    if args.human and not args.json:
        print(_format_human(result))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
