#!/usr/bin/env python3
"""cost_guard.py -- a FAIL-OPEN spend guard for the plugin's optional paid connectors.

The free, built-in, stdlib-only Tier-2 path is the product (see
references/CAPABILITY-TIERS.md). Paid connectors (DataForSEO, Firecrawl, Semrush,
Moz, ...) are accelerators, never requirements. This guard lets a skill estimate
what a paid call would cost, approve/deny it against a daily cap, log what was
spent, and read the running total -- so a connector can be used deliberately,
within a budget, instead of unbounded.

THE LOAD-BEARING INVARIANT -- FAIL-OPEN (ENGINE-CONTRACTS S15 / MASTER-PLAN MF-4):
    The guard must NEVER block a deliverable. If the ledger is missing, corrupt,
    or unreadable -- or if ANY cost-guard error occurs -- the guard falls through
    to "allow / free-Tier-2" and exits 0, rather than raising. A connector-safety
    bug must never take down the free path. Over-cap is a legitimate *deny of the
    paid call* (the free Tier-2 deliverable still ships); it is a decision, not an
    error, and it likewise never raises.

    The ONE thing that exits non-zero is bad CLI input (a caller mistake, not a
    ledger problem) -- and even then it prints a JSON error object, never a raw
    traceback.

OUR OWN SCHEMA (not any third-party cost/cents model):
    Costs are abstract "credits" -- a plugin-local estimate unit, deliberately NOT
    a vendor's cents/quota schema. The per-connector rates below are our own coarse
    estimates for budgeting only; they are not billed and are not authoritative.

    The ledger is a small JSON file we own:
        {"version": 1, "entries": [
            {"date": "YYYY-MM-DD", "connector": "dataforseo", "units": 2, "cost": 0.6},
            ...]}

Output (ENGINE-CONTRACTS): JSON to stdout by default; `--human` prints an ASCII
summary. Deterministic (same input -> same output; pass --date to pin the day).
Offline by construction (no network); `--no-network` is accepted as a harmless
no-op so the script honors the offline contract. ASCII-safe throughout.

Usage:
  py cost_guard.py estimate --connector dataforseo --units 3
  py cost_guard.py approve  --connector dataforseo --units 1 --cap 5 [--ledger PATH] [--date YYYY-MM-DD]
  py cost_guard.py log      --connector dataforseo --units 1 [--cost 0.3] [--ledger PATH] [--date YYYY-MM-DD]
  py cost_guard.py total    [--ledger PATH] [--date YYYY-MM-DD] [--all]
  (add --human to any subcommand for an ASCII summary)
"""
import argparse
import datetime
import json
import math
import os
import sys

# --- our own tier/estimate table (abstract "credits", NOT a vendor cents schema) ---
# unit_cost is a coarse plugin-local budgeting estimate per call-unit. Free-keyed
# connectors (Google PSI/CrUX, GSC, Bing Webmaster) cost 0 -- they are free Tier-1
# deepeners, listed here only so callers get a uniform answer.
UNIT = "credits"
TIER_TABLE = {
    "dataforseo": {"tier": 1, "unit_cost": 0.30},
    "firecrawl":  {"tier": 1, "unit_cost": 0.20},
    "semrush":    {"tier": 1, "unit_cost": 0.50},
    "moz":        {"tier": 1, "unit_cost": 0.25},
    "bing":       {"tier": 1, "unit_cost": 0.00},
    "google":     {"tier": 1, "unit_cost": 0.00},
    "gsc":        {"tier": 1, "unit_cost": 0.00},
    "crux":       {"tier": 1, "unit_cost": 0.00},
}
# An unrecognized connector is NOT an error (the roster is open-ended); it falls back
# to a conservative default estimate so the guard still gives a usable number.
DEFAULT_RATE = {"tier": 1, "unit_cost": 0.10}

LEDGER_VERSION = 1
# free path that a denied/failed-open paid call degrades to -- never blocks a deliverable.
FALLBACK = "free-tier-2"


class BadInput(Exception):
    """Raised for a CALLER mistake (bad CLI args). Distinct from any ledger problem,
    which is always handled fail-open. Surfaces as a JSON error + non-zero exit."""


def _round(x):
    """Deterministic, JSON-clean rounding for credit amounts."""
    return round(float(x), 4)


def default_ledger_path():
    """Where the ledger lives by DEFAULT -- under the user's home (their workspace),
    NEVER inside the plugin install. Overridable with the DPS_COST_LEDGER env var or
    the --ledger flag. We deliberately do not anchor to this file's directory (that
    would put writable state inside the read-only plugin)."""
    override = os.environ.get("DPS_COST_LEDGER")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".designer-pro-and-seo",
                        "cost_ledger.json")


def _today():
    """Today's date (UTC) as an ISO string. The day is an implicit input; callers
    pin it with --date for fully deterministic output."""
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


# --------------------------------------------------------------------------- #
# estimate                                                                     #
# --------------------------------------------------------------------------- #
def estimate_call(connector, units=1):
    """Estimate the cost (in our own credits) of one paid call of `units` size.
    Pure + deterministic; never touches the ledger or the network."""
    key = (connector or "").strip().lower()
    known = key in TIER_TABLE
    rate = TIER_TABLE.get(key, DEFAULT_RATE)
    cost = _round(rate["unit_cost"] * units)
    return {
        "connector": key,
        "tier": rate["tier"],
        "units": units,
        "unit": UNIT,
        "unit_cost": _round(rate["unit_cost"]),
        "estimated_cost": cost,
        "known_connector": known,
    }


# --------------------------------------------------------------------------- #
# ledger I/O -- every reader is FAIL-OPEN: it never raises, it returns a warning #
# --------------------------------------------------------------------------- #
def _empty_ledger():
    return {"version": LEDGER_VERSION, "entries": []}


def load_ledger(path):
    """Return (ledger_dict, warning_or_None). NEVER raises.

      * file does not exist  -> (empty ledger, None)   # normal first-run state
      * unreadable / corrupt / wrong-shape -> (empty ledger, warning string)

    A non-None warning is the fail-open signal: the caller should ALLOW and surface
    the warning, because we could not trust the recorded total."""
    if not os.path.exists(path):
        return _empty_ledger(), None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        return _empty_ledger(), "ledger unreadable or corrupt (%s); failing open" % (
            type(exc).__name__,)
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return _empty_ledger(), "ledger has an unexpected shape; failing open"
    # A non-finite (NaN/Infinity, including a literal token or an overflowing 1e999) or
    # otherwise unparseable cost makes the recorded total untrustworthy: fail open
    # (allow) rather than let an Inf/NaN reach a cap comparison (which would wrongly DENY)
    # or json.dumps (which would emit invalid JSON). Never deny on a corrupt ledger.
    for e in data["entries"]:
        if isinstance(e, dict) and "cost" in e:
            try:
                val = float(e["cost"])
            except (TypeError, ValueError):
                return _empty_ledger(), "ledger has an unparseable cost value; failing open"
            if not math.isfinite(val):
                return _empty_ledger(), "ledger has a non-finite cost value; failing open"
    return data, None


def _entry_cost(entry):
    """Cost of one ledger entry, tolerant of a missing/garbage cost field."""
    try:
        return float(entry.get("cost", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _sum_costs(ledger, date=None):
    """Sum entry costs (optionally for one `date`), WATCHING FOR OVERFLOW. Returns
    (total, finite_ok). Even when every INDIVIDUAL cost is finite (so load_ledger passes
    it), a long ledger of large costs can overflow the running sum to +inf; finite_ok goes
    False the moment that happens. Callers must FAIL OPEN on a non-finite total instead of
    denying on -- or emitting -- an Inf/NaN (MASTER-PLAN MF-4 / ENGINE-CONTRACTS S15)."""
    total = 0.0
    for e in ledger.get("entries", []):
        if not isinstance(e, dict):
            continue
        if date is not None and e.get("date") != date:
            continue
        total += _entry_cost(e)
        if not math.isfinite(total):
            return total, False
    return total, math.isfinite(total)


def daily_total(ledger, date):
    """Sum of credits recorded for `date`. Tolerant of malformed individual entries.
    Returns a non-finite value (which output/decision paths must guard via _guarded_total)
    only when the sum itself overflows."""
    total, ok = _sum_costs(ledger, date)
    return _round(total) if ok else total


def grand_total(ledger):
    """Sum of credits across every recorded date (see daily_total for the overflow note)."""
    total, ok = _sum_costs(ledger)
    return _round(total) if ok else total


def _guarded_total(ledger, date=None):
    """(value, warning): a FINITE rounded total, or (None, warning) when the aggregate is
    non-finite (cost overflow) -- so a caller fails open and never serializes Infinity/NaN
    into its JSON output. Every output/decision path that reports a total goes through this."""
    total, ok = _sum_costs(ledger, date)
    if not ok:
        return None, "ledger total is non-finite (cost overflow); failing open"
    return _round(total), None


def append_entry(ledger_path, connector, units, cost, date):
    """Log one call to the ledger. FAIL-OPEN: a corrupt existing ledger is replaced
    with a fresh one (warned), and a write failure is warned but never raised. Always
    returns a result dict; `logged` says whether it actually persisted."""
    est = estimate_call(connector, units)
    use_cost = est["estimated_cost"] if cost is None else _round(cost)
    ledger, warn = load_ledger(ledger_path)
    warnings = []
    if warn:
        warnings.append(warn + " -- starting a fresh ledger")
    entry = {"date": date, "connector": est["connector"], "units": units,
             "cost": use_cost}
    ledger.setdefault("entries", []).append(entry)
    ledger.setdefault("version", LEDGER_VERSION)

    logged = True
    try:
        parent = os.path.dirname(os.path.abspath(ledger_path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2, sort_keys=True)
    except OSError as exc:
        logged = False
        warnings.append("could not persist ledger (%s); continuing" % type(exc).__name__)

    # Guarded totals: a non-finite aggregate (overflow of many finite costs) reports as
    # null with a warning rather than an Infinity/NaN JSON token. Still fail-open (logged).
    daily_val, daily_warn = _guarded_total(ledger, date)
    grand_val, grand_warn = _guarded_total(ledger)
    for w in (daily_warn, grand_warn):
        if w and w not in warnings:
            warnings.append(w)

    return {
        "connector": est["connector"],
        "units": units,
        "cost": use_cost,
        "unit": UNIT,
        "date": date,
        "logged": logged,
        "daily_total": daily_val,
        "grand_total": grand_val,
        "ledger": ledger_path,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------- #
# approve / deny against a daily cap -- FAIL-OPEN                              #
# --------------------------------------------------------------------------- #
def decide(connector, units, cap, ledger_path, date):
    """Decide whether a paid call is within the daily cap. NEVER raises.

    decision == "allow": within budget -> the paid call may proceed.
    decision == "deny" : would exceed the daily cap -> DO NOT make the paid call;
                         fall through to the free Tier-2 path. The deliverable ships.
    fail_open == True  : the ledger was unreadable/corrupt (or no cap was given), so
                         we could not enforce a budget and ALLOW by design rather
                         than block. Always paired with a warning."""
    est = estimate_call(connector, units)
    ledger, warn = load_ledger(ledger_path)
    warnings = []

    base = {
        "connector": est["connector"],
        "units": units,
        "unit": UNIT,
        "estimated_cost": est["estimated_cost"],
        "cap": (None if cap is None else _round(cap)),
        "date": date,
        "fallback": FALLBACK,
    }

    if warn:
        # Corrupt/unreadable ledger -> cannot trust the total -> fail open (allow).
        warnings.append(warn)
        base.update({"daily_total_before": None, "projected_total": None,
                     "decision": "allow", "fail_open": True, "warnings": warnings})
        return base

    before, before_warn = _guarded_total(ledger, date)
    if before_warn:
        # The summed daily total overflowed to non-finite even though every individual
        # cost was finite: cannot enforce a budget -> fail open (allow), never DENY.
        warnings.append(before_warn)
        base.update({"daily_total_before": None, "projected_total": None,
                     "decision": "allow", "fail_open": True, "warnings": warnings})
        return base

    projected_raw = before + est["estimated_cost"]
    if not math.isfinite(projected_raw):
        # the projection itself overflowed -> same fail-open posture.
        warnings.append("projected total is non-finite (cost overflow); failing open")
        base.update({"daily_total_before": before, "projected_total": None,
                     "decision": "allow", "fail_open": True, "warnings": warnings})
        return base
    projected = _round(projected_raw)

    if cap is None:
        warnings.append("no daily cap configured; allowing (free path stays the fallback)")
        base.update({"daily_total_before": before, "projected_total": projected,
                     "decision": "allow", "fail_open": True, "warnings": warnings})
        return base

    decision = "allow" if projected <= _round(cap) else "deny"
    if decision == "deny":
        warnings.append("daily cap %s would be exceeded (projected %s); use the free "
                        "Tier-2 path" % (_round(cap), projected))
    base.update({"daily_total_before": before, "projected_total": projected,
                 "decision": decision, "fail_open": False, "warnings": warnings})
    return base


# --------------------------------------------------------------------------- #
# CLI plumbing                                                                 #
# --------------------------------------------------------------------------- #
class _JsonArgumentParser(argparse.ArgumentParser):
    """argparse that reports structural errors as a JSON error object on stdout and
    exits non-zero -- so even a malformed command line never yields a raw traceback
    and the output stays machine-parseable."""

    def error(self, message):
        print(json.dumps({"ok": False, "error": str(message)}, sort_keys=True))
        self.exit(2)


def _validate_units(units):
    if units < 0:
        raise BadInput("units must be >= 0 (got %s)" % units)
    return units


def _validate_cost(cost):
    # A non-finite CLI float (argparse parses 'inf'/'nan' without error) is a CALLER
    # mistake -> BadInput (JSON error + non-zero), never a silent Inf/NaN in the ledger.
    if cost is not None and not math.isfinite(cost):
        raise BadInput("cost must be a finite number (got %s)" % cost)
    if cost is not None and cost < 0:
        raise BadInput("cost must be >= 0 (got %s)" % cost)
    return cost


def _validate_cap(cap):
    if cap is not None and not math.isfinite(cap):
        raise BadInput("cap must be a finite number (got %s)" % cap)
    if cap is not None and cap < 0:
        raise BadInput("cap must be >= 0 (got %s)" % cap)
    return cap


def _human(action, result):
    """ASCII-only summary of a result dict."""
    lines = ["cost_guard: %s" % action, "=" * (12 + len(action))]
    order = ["connector", "units", "unit_cost", "estimated_cost", "cost",
             "decision", "fail_open", "cap", "daily_total_before",
             "projected_total", "daily_total", "grand_total", "date",
             "logged", "fallback", "ledger"]
    for k in order:
        if k in result and result[k] is not None:
            lines.append("  %-18s: %s" % (k, result[k]))
    for w in result.get("warnings", []):
        lines.append("  warning           : %s" % w)
    text = "\n".join(lines)
    return text.encode("ascii", "replace").decode("ascii")


def _emit(action, result, human, exit_code=0):
    result = dict(result)
    result.setdefault("ok", True)
    result["action"] = action
    if human:
        print(_human(action, result))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code


def _cmd_estimate(args):
    units = _validate_units(args.units)
    return _emit("estimate", estimate_call(args.connector, units), args.human)


def _cmd_approve(args):
    units = _validate_units(args.units)
    cap = _validate_cap(args.cap)
    date = args.date or _today()
    return _emit("approve", decide(args.connector, units, cap, args.ledger, date),
                 args.human)


def _cmd_log(args):
    units = _validate_units(args.units)
    cost = _validate_cost(args.cost)
    date = args.date or _today()
    return _emit("log", append_entry(args.ledger, args.connector, units, cost, date),
                 args.human)


def _cmd_total(args):
    ledger, warn = load_ledger(args.ledger)
    date = args.date or _today()
    warnings = [warn] if warn else []
    # Guarded totals so an aggregate overflow reports as null + warning (fail-open), never
    # an Infinity/NaN token in the JSON.
    if args.all:
        daily_val, scope_warn = _guarded_total(ledger)
    else:
        daily_val, scope_warn = _guarded_total(ledger, date)
    grand_val, grand_warn = _guarded_total(ledger)
    for w in (scope_warn, grand_warn):
        if w and w not in warnings:
            warnings.append(w)
    result = {
        "date": (None if args.all else date),
        "daily_total": daily_val,
        "grand_total": grand_val,
        "entry_count": len(ledger.get("entries", [])),
        "ledger": args.ledger,
        "fail_open": bool(warn) or bool(scope_warn) or bool(grand_warn),
        "warnings": warnings,
    }
    return _emit("total", result, args.human)


def _build_parser():
    p = _JsonArgumentParser(
        description="Fail-open spend guard for optional paid connectors.")
    sub = p.add_subparsers(dest="command")
    sub.required = True  # missing subcommand -> JSON error via _JsonArgumentParser

    def _common(sp, *, ledger=False):
        sp.add_argument("--human", action="store_true",
                        help="ASCII summary instead of JSON")
        sp.add_argument("--no-network", action="store_true",
                        help="accepted no-op (this guard never uses the network)")
        if ledger:
            sp.add_argument("--ledger", default=default_ledger_path(),
                            help="path to the JSON ledger (default: under the user home)")
            sp.add_argument("--date", default=None,
                            help="pin the day as YYYY-MM-DD (default: today, UTC)")

    pe = sub.add_parser("estimate", help="estimate a paid call's cost")
    pe.add_argument("--connector", required=True)
    pe.add_argument("--units", type=int, default=1)
    _common(pe)
    pe.set_defaults(func=_cmd_estimate)

    pa = sub.add_parser("approve", help="approve/deny a paid call against a daily cap")
    pa.add_argument("--connector", required=True)
    pa.add_argument("--units", type=int, default=1)
    pa.add_argument("--cap", type=float, default=None,
                    help="daily cap in credits; absent -> fail-open allow")
    _common(pa, ledger=True)
    pa.set_defaults(func=_cmd_approve)

    pl = sub.add_parser("log", help="record a paid call in the ledger")
    pl.add_argument("--connector", required=True)
    pl.add_argument("--units", type=int, default=1)
    pl.add_argument("--cost", type=float, default=None,
                    help="explicit cost in credits; absent -> use the estimate")
    _common(pl, ledger=True)
    pl.set_defaults(func=_cmd_log)

    pt = sub.add_parser("total", help="show the running total")
    pt.add_argument("--all", action="store_true",
                    help="report the all-time total instead of just today's")
    _common(pt, ledger=True)
    pt.set_defaults(func=_cmd_total)

    return p


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)  # structural errors -> JSON error + SystemExit(2)
    try:
        return args.func(args)
    except BadInput as exc:
        # A caller mistake (not a ledger problem): JSON error, non-zero exit.
        print(json.dumps({"ok": False, "action": args.command, "error": str(exc)},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
