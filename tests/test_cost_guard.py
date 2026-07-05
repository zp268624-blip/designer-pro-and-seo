"""Tests for scripts/workflow/cost_guard.py -- the FAIL-OPEN spend guard for paid
connectors.

The single load-bearing invariant: the guard must NEVER block a deliverable. If the
ledger is missing, corrupt, or unreadable -- or any cost-guard error occurs -- it
falls through to "allow / free-Tier-2" and exits 0, rather than raising. Over-cap is
a legitimate DENY of the *paid* call (the free Tier-2 path still ships), and it must
never error. Daily totals accumulate per date. Bad CLI input (not a ledger problem)
is the one case that exits non-zero, with a JSON error object (never a traceback).

Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/`. No pip
install, no network: every case uses a tempdir ledger and an explicit --date, so the
output is deterministic.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "workflow"))
import cost_guard  # noqa: E402

DATE = "2026-06-30"
DATE2 = "2026-07-01"


def _reject_const(c):
    """json.loads parse_constant hook: raise on any non-finite token (Infinity / NaN /
    -Infinity) so a test can prove the output is STRICT JSON, not just loadable by Python."""
    raise ValueError("non-finite JSON token emitted: %s" % c)


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dps_cost_")
        self.ledger = os.path.join(self.tmp, "cost_ledger.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, text):
        with open(self.ledger, "w", encoding="utf-8") as f:
            f.write(text)

    def _run(self, argv):
        """Run main(argv), capture stdout, return (exit_code, parsed_json_or_text)."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cost_guard.main(argv)
        out = buf.getvalue()
        try:
            return code, json.loads(out)
        except ValueError:
            return code, out


# --------------------------------------------------------------------------- #
# estimate -- our own tier/credit table, deterministic                        #
# --------------------------------------------------------------------------- #
class EstimateTest(_Base):
    def test_estimate_is_deterministic(self):
        a = cost_guard.estimate_call("dataforseo", 2)
        b = cost_guard.estimate_call("dataforseo", 2)
        self.assertEqual(a, b)
        self.assertTrue(a["known_connector"])
        self.assertEqual(a["estimated_cost"], round(a["unit_cost"] * 2, 4))

    def test_unknown_connector_uses_default_not_error(self):
        r = cost_guard.estimate_call("totally-made-up", 1)
        self.assertFalse(r["known_connector"])
        self.assertGreaterEqual(r["estimated_cost"], 0.0)

    def test_estimate_cli_ok(self):
        code, obj = self._run(["estimate", "--connector", "firecrawl", "--units", "3"])
        self.assertEqual(code, 0)
        self.assertTrue(obj["ok"])
        self.assertEqual(obj["action"], "estimate")


# --------------------------------------------------------------------------- #
# FAIL-OPEN: a corrupt / garbage ledger still ALLOWS (the core invariant)      #
# --------------------------------------------------------------------------- #
class FailOpenTest(_Base):
    def test_corrupt_ledger_approve_fails_open_allow(self):
        # Garbage that is not JSON at all.
        self._write("}{ this is not json at all \x00\x01")
        res = cost_guard.decide("dataforseo", 1, cap=0.01,
                                ledger_path=self.ledger, date=DATE)
        # Even with a cap of 0.01 (which would normally DENY), a corrupt ledger
        # forces fail-open: allow.
        self.assertEqual(res["decision"], "allow")
        self.assertTrue(res["fail_open"])
        self.assertTrue(res["warnings"])

    def test_corrupt_ledger_approve_cli_exits_zero(self):
        self._write("not json")
        code, obj = self._run(["approve", "--connector", "dataforseo",
                               "--units", "1", "--cap", "0.01",
                               "--ledger", self.ledger, "--date", DATE])
        self.assertEqual(code, 0)            # never blocks
        self.assertTrue(obj["ok"])
        self.assertEqual(obj["decision"], "allow")
        self.assertTrue(obj["fail_open"])

    def test_corrupt_ledger_total_fails_open_zero(self):
        self._write("@@@garbage@@@")
        code, obj = self._run(["total", "--ledger", self.ledger, "--date", DATE])
        self.assertEqual(code, 0)
        self.assertTrue(obj["ok"])
        self.assertEqual(obj["daily_total"], 0.0)
        self.assertTrue(obj["warnings"])

    def test_missing_ledger_is_not_an_error(self):
        # A missing ledger is the NORMAL first-run state -- allow, but NOT a fail_open
        # warning (nothing is broken; the running total is simply 0).
        self.assertFalse(os.path.exists(self.ledger))
        res = cost_guard.decide("dataforseo", 1, cap=100.0,
                                ledger_path=self.ledger, date=DATE)
        self.assertEqual(res["decision"], "allow")
        self.assertFalse(res["fail_open"])
        self.assertEqual(res["daily_total_before"], 0.0)

    def test_log_to_corrupt_ledger_does_not_raise(self):
        self._write("corrupt!!!")
        code, obj = self._run(["log", "--connector", "moz", "--units", "1",
                               "--ledger", self.ledger, "--date", DATE])
        self.assertEqual(code, 0)
        self.assertTrue(obj["ok"])

    # --- FIX 5: non-finite (NaN/Infinity) ledger values fail OPEN ------------
    def test_infinity_ledger_cost_fails_open_allow(self):
        # JSON parses the literal token `Infinity`; a non-finite recorded total is
        # corrupt -> fail open (allow), never DENY, even under a tiny cap.
        self._write('{"version": 1, "entries": '
                    '[{"date": "%s", "connector": "moz", "units": 1, "cost": Infinity}]}'
                    % DATE)
        res = cost_guard.decide("dataforseo", 1, cap=0.01,
                                ledger_path=self.ledger, date=DATE)
        self.assertEqual(res["decision"], "allow")
        self.assertTrue(res["fail_open"])
        self.assertTrue(res["warnings"])

    def test_nan_ledger_cost_fails_open_and_emits_valid_json(self):
        self._write('{"version": 1, "entries": '
                    '[{"date": "%s", "connector": "moz", "units": 1, "cost": NaN}]}'
                    % DATE)
        code, obj = self._run(["approve", "--connector", "dataforseo", "--units", "1",
                               "--cap", "0.01", "--ledger", self.ledger, "--date", DATE])
        self.assertEqual(code, 0)              # never blocks the deliverable
        self.assertIsInstance(obj, dict)       # output parsed as valid JSON (no NaN/Inf token)
        self.assertEqual(obj["decision"], "allow")
        self.assertTrue(obj["fail_open"])

    def test_overflow_ledger_cost_fails_open(self):
        # 1e999 overflows JSON to inf without being a literal Infinity token.
        self._write('{"version": 1, "entries": '
                    '[{"date": "%s", "connector": "moz", "units": 1, "cost": 1e999}]}'
                    % DATE)
        ledger, warn = cost_guard.load_ledger(self.ledger)
        self.assertIsNotNone(warn)             # flagged corrupt -> fail open
        self.assertEqual(cost_guard.daily_total(ledger, DATE), 0.0)

    def test_total_on_nonfinite_ledger_exits_zero(self):
        self._write('{"version": 1, "entries": '
                    '[{"date": "%s", "connector": "moz", "cost": Infinity}]}' % DATE)
        code, obj = self._run(["total", "--ledger", self.ledger, "--date", DATE])
        self.assertEqual(code, 0)
        self.assertEqual(obj["daily_total"], 0.0)
        self.assertTrue(obj["warnings"])

    # --- FIX 2: aggregate overflow of many FINITE costs fails OPEN -----------
    def _write_big_ledger(self, n=5, big=1e308):
        # Each cost is FINITE (passes load_ledger's per-entry isfinite check), but their
        # SUM overflows to +inf -- the aggregate-overflow hole FIX 2 closes.
        entries = ",".join(
            '{"date": "%s", "connector": "moz", "units": 1, "cost": %r}' % (DATE, big)
            for _ in range(n))
        self._write('{"version": 1, "entries": [%s]}' % entries)

    def test_aggregate_overflow_load_ledger_does_not_flag(self):
        # the individual costs are finite, so the per-entry guard must NOT fire here --
        # this proves the overflow is a NEW failure mode the aggregate guard must catch.
        self._write_big_ledger()
        ledger, warn = cost_guard.load_ledger(self.ledger)
        self.assertIsNone(warn)
        self.assertEqual(len(ledger["entries"]), 5)

    def test_aggregate_overflow_decide_fails_open_allow(self):
        self._write_big_ledger()
        res = cost_guard.decide("dataforseo", 1, cap=0.01,
                                ledger_path=self.ledger, date=DATE)
        self.assertEqual(res["decision"], "allow")   # fail-open, never DENY on overflow
        self.assertTrue(res["fail_open"])
        self.assertTrue(res["warnings"])

    def test_aggregate_overflow_approve_cli_emits_valid_json(self):
        self._write_big_ledger()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cost_guard.main(["approve", "--connector", "dataforseo", "--units", "1",
                                    "--cap", "0.01", "--ledger", self.ledger, "--date", DATE])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertNotIn("Infinity", out)
        self.assertNotIn("NaN", out)
        obj = json.loads(out, parse_constant=_reject_const)   # strict: no non-finite token
        self.assertEqual(obj["decision"], "allow")
        self.assertTrue(obj["fail_open"])

    def test_aggregate_overflow_total_cli_emits_valid_json(self):
        self._write_big_ledger()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cost_guard.main(["total", "--ledger", self.ledger, "--date", DATE])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertNotIn("Infinity", out)
        self.assertNotIn("NaN", out)
        obj = json.loads(out, parse_constant=_reject_const)
        self.assertTrue(obj.get("fail_open") or obj.get("warnings"))

    def test_aggregate_overflow_log_cli_emits_valid_json(self):
        self._write_big_ledger()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cost_guard.main(["log", "--connector", "moz", "--units", "1",
                                    "--ledger", self.ledger, "--date", DATE])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertNotIn("Infinity", out)
        self.assertNotIn("NaN", out)
        json.loads(out, parse_constant=_reject_const)   # must be strict JSON


# --------------------------------------------------------------------------- #
# Over-cap DENIES the paid call (but never errors)                            #
# --------------------------------------------------------------------------- #
class CapTest(_Base):
    def test_over_cap_denies_without_error(self):
        # Spend up to/over a small cap, then try one more paid call.
        cost_guard.append_entry(self.ledger, "dataforseo", 4, None, DATE)  # 4 * 0.30 = 1.20
        res = cost_guard.decide("dataforseo", 1, cap=1.0,
                                ledger_path=self.ledger, date=DATE)
        self.assertEqual(res["decision"], "deny")
        self.assertFalse(res["fail_open"])           # a clean deny, not an error
        self.assertGreater(res["projected_total"], res["cap"])

    def test_under_cap_allows(self):
        cost_guard.append_entry(self.ledger, "dataforseo", 1, None, DATE)  # 0.30
        res = cost_guard.decide("dataforseo", 1, cap=100.0,
                                ledger_path=self.ledger, date=DATE)
        self.assertEqual(res["decision"], "allow")

    def test_over_cap_cli_still_exits_zero(self):
        cost_guard.append_entry(self.ledger, "semrush", 5, None, DATE)
        code, obj = self._run(["approve", "--connector", "semrush", "--units", "1",
                               "--cap", "0.5", "--ledger", self.ledger,
                               "--date", DATE])
        self.assertEqual(code, 0)               # deny is not a failure exit
        self.assertEqual(obj["decision"], "deny")


# --------------------------------------------------------------------------- #
# Ledger accounting: daily totals accumulate, per-date                        #
# --------------------------------------------------------------------------- #
class LedgerTest(_Base):
    def test_daily_total_accumulates(self):
        r1 = cost_guard.append_entry(self.ledger, "dataforseo", 1, None, DATE)  # 0.30
        r2 = cost_guard.append_entry(self.ledger, "dataforseo", 1, None, DATE)  # 0.30
        self.assertEqual(r1["daily_total"], 0.3)
        self.assertEqual(r2["daily_total"], 0.6)

    def test_total_is_scoped_to_date(self):
        cost_guard.append_entry(self.ledger, "dataforseo", 1, None, DATE)    # 0.30 today
        cost_guard.append_entry(self.ledger, "dataforseo", 2, None, DATE2)   # 0.60 next day
        ledger, warn = cost_guard.load_ledger(self.ledger)
        self.assertIsNone(warn)
        self.assertEqual(cost_guard.daily_total(ledger, DATE), 0.3)
        self.assertEqual(cost_guard.daily_total(ledger, DATE2), 0.6)
        self.assertEqual(cost_guard.grand_total(ledger), 0.9)

    def test_explicit_cost_override_is_logged(self):
        r = cost_guard.append_entry(self.ledger, "dataforseo", 1, 2.5, DATE)
        self.assertEqual(r["daily_total"], 2.5)

    def test_total_cli_reports_running_total(self):
        cost_guard.append_entry(self.ledger, "moz", 2, None, DATE)  # 2 * 0.25 = 0.50
        code, obj = self._run(["total", "--ledger", self.ledger, "--date", DATE])
        self.assertEqual(code, 0)
        self.assertEqual(obj["daily_total"], 0.5)


# --------------------------------------------------------------------------- #
# Bad CLI input -> non-zero + JSON error (this is NOT the fail-open path)      #
# --------------------------------------------------------------------------- #
class BadInputTest(_Base):
    def test_negative_units_is_a_json_error(self):
        code, obj = self._run(["estimate", "--connector", "moz", "--units", "-3"])
        self.assertNotEqual(code, 0)
        self.assertIsInstance(obj, dict)
        self.assertFalse(obj["ok"])
        self.assertIn("error", obj)

    def test_negative_cap_is_a_json_error(self):
        code, obj = self._run(["approve", "--connector", "moz", "--units", "1",
                               "--cap", "-5", "--ledger", self.ledger, "--date", DATE])
        self.assertNotEqual(code, 0)
        self.assertFalse(obj["ok"])

    def test_nonfinite_cap_is_a_json_error(self):
        # argparse parses 'inf' to float('inf'); a non-finite CLI float is a caller
        # mistake -> JSON error + non-zero (NOT the ledger fail-open path).
        code, obj = self._run(["approve", "--connector", "moz", "--units", "1",
                               "--cap", "inf", "--ledger", self.ledger, "--date", DATE])
        self.assertNotEqual(code, 0)
        self.assertIsInstance(obj, dict)
        self.assertFalse(obj["ok"])

    def test_nonfinite_cost_is_a_json_error(self):
        code, obj = self._run(["log", "--connector", "moz", "--units", "1",
                               "--cost", "nan", "--ledger", self.ledger, "--date", DATE])
        self.assertNotEqual(code, 0)
        self.assertIsInstance(obj, dict)
        self.assertFalse(obj["ok"])

    def test_unknown_subcommand_exits_nonzero_json(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit) as cm:
                cost_guard.main(["frobnicate"])
        self.assertNotEqual(cm.exception.code, 0)
        obj = json.loads(buf.getvalue())
        self.assertFalse(obj["ok"])


# --------------------------------------------------------------------------- #
# Offline / human contract                                                    #
# --------------------------------------------------------------------------- #
class ContractTest(_Base):
    def test_no_network_flag_accepted_and_offline(self):
        code, obj = self._run(["total", "--ledger", self.ledger, "--date", DATE,
                               "--no-network"])
        self.assertEqual(code, 0)
        self.assertTrue(obj["ok"])

    def test_human_output_is_ascii(self):
        cost_guard.append_entry(self.ledger, "moz", 1, None, DATE)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cost_guard.main(["total", "--ledger", self.ledger,
                                    "--date", DATE, "--human"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        out.encode("ascii")  # must not raise

    def test_default_ledger_path_is_outside_the_plugin(self):
        p = os.path.abspath(cost_guard.default_ledger_path())
        plugin_root = os.path.abspath(ROOT)
        self.assertFalse(p.startswith(plugin_root + os.sep),
                         "default ledger must live outside the plugin: %s" % p)


if __name__ == "__main__":
    unittest.main()
