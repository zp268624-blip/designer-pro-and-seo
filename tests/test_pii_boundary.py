"""C-PII / workspace-boundary tests (MASTER-PLAN 11.4) for the two skills most likely to
touch PII: csv-to-report (script-enforced) and client-outreach (prose contract).

Script-enforced properties are exercised against scripts/workflow/csv_to_report.py on
adversarial input. Properties that are prose-only (not enforced by a script) are asserted
against the contract text and clearly marked as such in the test name + docstring.

Behavior under review (Codex round 1, FIX 11): csv_to_report now redacts BY DEFAULT both
credential columns AND contact-PII columns AND any email/phone-looking VALUE. --show-pii
opts out of the contact-PII redaction; credentials stay redacted regardless. --show-sensitive
opts out of credential redaction only.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_TO_REPORT = os.path.join(ROOT, "scripts", "workflow", "csv_to_report.py")

# Columns whose VALUES csv_to_report.py must redact by default (credentials/secrets).
CRED_COLS = ["password", "token", "api_key", "secret",
             "access_key", "private_key", "ssn", "cvv", "auth"]
# Contact-PII columns now redacted by default too (opt out with --show-pii).
CONTACT_PII_COLS = ["email", "phone"]
# An UNCLASSIFIED column (header matches neither set) whose VALUES look like PII, to exercise
# value-level masking independent of the header name.
PII_VALUE_COL = "bio"
EMAIL_VALUES = ["alice@example.test", "bob@example.test"]
PHONE_VALUES = ["+1-555-0100", "+1-555-0199"]
BIO_VALUES = ["reach me at zoe@example.test", "ring 555-867-5309 any time"]
BIO_PII_TOKENS = ["zoe@example.test", "555-867-5309"]


def _sentinel(col):
    return "ZZSENTINEL-" + col  # non-numeric -> categorical -> redacted iff sensitive


def _write_adversarial_csv(path):
    cols = ["name"] + CONTACT_PII_COLS + [PII_VALUE_COL] + CRED_COLS
    rows = [
        ["alice", EMAIL_VALUES[0], PHONE_VALUES[0], BIO_VALUES[0]] + [_sentinel(c) for c in CRED_COLS],
        ["bob", EMAIL_VALUES[1], PHONE_VALUES[1], BIO_VALUES[1]] + [_sentinel(c) for c in CRED_COLS],
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(r) + "\n")
    return cols


def _run(csv_path, extra=None, cwd=None):
    cmd = [sys.executable, CSV_TO_REPORT, "--in", csv_path] + (extra or [])
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", cwd=cwd)
    return r


class CsvToReportRedactionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dps_pii_")
        self.addCleanup(_rmtree, self.tmp)
        self.csv = os.path.join(self.tmp, "contacts.csv")
        _write_adversarial_csv(self.csv)

    def _report(self, extra=None):
        r = _run(self.csv, extra=extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout, json.loads(r.stdout)

    # --- credentials (unchanged contract) -------------------------------------
    def test_credential_columns_are_redacted_by_default(self):
        stdout, rep = self._report()
        bycol = {c["column"]: c for c in rep["columns"]}
        for col in CRED_COLS:
            self.assertIn(col, bycol)
            self.assertTrue(bycol[col].get("redacted"),
                            "%s should be redacted by default" % col)
            for tv in bycol[col].get("top_values", []):
                self.assertEqual(tv["value"], "[redacted]")

    def test_no_secret_value_is_ever_emitted(self):
        stdout, _ = self._report()
        for col in CRED_COLS:
            self.assertNotIn(_sentinel(col), stdout,
                             "secret VALUE for %s leaked into output" % col)

    def test_human_mode_also_redacts(self):
        r = _run(self.csv, extra=["--human"])
        self.assertEqual(r.returncode, 0, r.stderr)
        for col in CRED_COLS:
            self.assertNotIn(_sentinel(col), r.stdout)

    # --- contact-PII columns + value-level masking (new default-on behavior) ---
    def test_contact_pii_columns_redacted_by_default(self):
        stdout, rep = self._report()
        bycol = {c["column"]: c for c in rep["columns"]}
        for col in CONTACT_PII_COLS:
            self.assertIn(col, bycol)
            self.assertTrue(bycol[col].get("redacted"),
                            "%s should be redacted by default" % col)

    def test_pii_looking_values_masked_in_unclassified_column(self):
        # The 'bio' header matches neither set, but its email/phone-looking VALUES are masked.
        stdout, rep = self._report()
        bycol = {c["column"]: c for c in rep["columns"]}
        self.assertTrue(bycol[PII_VALUE_COL].get("redacted"),
                        "value-level PII masking should mark the bio column redacted")
        for tok in BIO_PII_TOKENS:
            self.assertNotIn(tok, stdout, "PII value %r leaked into output" % tok)

    def test_no_pii_value_is_ever_emitted_by_default(self):
        stdout, _ = self._report()
        for tok in EMAIL_VALUES + PHONE_VALUES + BIO_PII_TOKENS:
            self.assertNotIn(tok, stdout, "PII value %r leaked by default" % tok)

    def test_show_pii_reveals_contact_columns_and_values(self):
        stdout, rep = self._report(extra=["--show-pii"])
        bycol = {c["column"]: c for c in rep["columns"]}
        for col in CONTACT_PII_COLS:
            self.assertFalse(bycol[col].get("redacted"),
                             "%s should be revealed with --show-pii" % col)
        self.assertIn(EMAIL_VALUES[0], stdout)
        for tok in BIO_PII_TOKENS:
            self.assertIn(tok, stdout, "%r should appear with --show-pii" % tok)

    def test_credentials_stay_redacted_with_show_pii(self):
        # --show-pii must NOT reveal credential columns.
        stdout, rep = self._report(extra=["--show-pii"])
        bycol = {c["column"]: c for c in rep["columns"]}
        for col in CRED_COLS:
            self.assertTrue(bycol[col].get("redacted"),
                            "%s must stay redacted even with --show-pii" % col)
            self.assertNotIn(_sentinel(col), stdout)

    def test_show_sensitive_override_is_opt_in(self):
        # --show-sensitive reveals credential columns; contact-PII stays redacted.
        stdout, rep = self._report(extra=["--show-sensitive"])
        self.assertIn(_sentinel("api_key"), stdout)
        bycol = {c["column"]: c for c in rep["columns"]}
        for col in CONTACT_PII_COLS:
            self.assertTrue(bycol[col].get("redacted"),
                            "--show-sensitive must not reveal contact-PII column %s" % col)

    def test_tool_writes_nothing_outside_stdout(self):
        run_dir = os.path.join(self.tmp, "rundir")
        os.makedirs(run_dir)
        before = set(os.listdir(run_dir))
        r = _run(self.csv, cwd=run_dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(set(os.listdir(run_dir)), before,
                         "csv_to_report must not write files into the working directory")

    def test_redaction_contract_documented_in_source(self):
        with open(CSV_TO_REPORT, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("redact", src.lower())
        self.assertIn("SENSITIVE", src)
        self.assertIn("CONTACT_PII", src)
        self.assertIn("--show-pii", src)

    # --- FIX B: redaction at the OTHER output paths (filter echo + group-by keys) -------
    def test_filter_on_pii_value_filters_for_real_but_redacts_echo(self):
        # --filter email=<real value> must MATCH on the real value (so row_count is correct)
        # yet NOT emit that value -- it is redacted in the `applied` echo by default.
        stdout, rep = self._report(extra=["--filter", "email=%s" % EMAIL_VALUES[0]])
        self.assertEqual(rep["row_count"], 1, "filter must still match on the REAL value")
        self.assertEqual(rep["applied"]["filter"]["email"], "[redacted]",
                         "filter echo must be redacted by default")
        self.assertNotIn(EMAIL_VALUES[0], stdout,
                         "filter value leaked through the applied echo by default")

    def test_filter_echo_reveals_value_with_show_pii(self):
        stdout, rep = self._report(extra=["--filter", "email=%s" % EMAIL_VALUES[0], "--show-pii"])
        self.assertEqual(rep["row_count"], 1)
        self.assertEqual(rep["applied"]["filter"]["email"], EMAIL_VALUES[0],
                         "--show-pii must reveal the real filter value")
        self.assertIn(EMAIL_VALUES[0], stdout)

    def test_group_by_pii_column_redacts_keys_by_default(self):
        # Grouping by a contact-PII column must group on the REAL keys (2 distinct emails ->
        # 2 groups) but emit each key redacted by default.
        stdout, rep = self._report(extra=["--group-by", "email"])
        groups = rep["group_by"]["groups"]
        self.assertEqual(len(groups), 2, "grouping must operate on the REAL keys")
        for g in groups:
            self.assertEqual(g["value"], "[redacted]", "group key leaked: %r" % g["value"])
        for v in EMAIL_VALUES:
            self.assertNotIn(v, stdout, "group key %r leaked into output" % v)

    def test_group_by_pii_column_reveals_keys_with_show_pii(self):
        stdout, rep = self._report(extra=["--group-by", "email", "--show-pii"])
        keys = sorted(g["value"] for g in rep["group_by"]["groups"])
        self.assertEqual(keys, sorted(EMAIL_VALUES),
                         "--show-pii must reveal the real group-by keys")

    def test_group_by_pii_column_redacts_in_human_mode(self):
        r = _run(self.csv, extra=["--group-by", "email", "--human"])
        self.assertEqual(r.returncode, 0, r.stderr)
        for v in EMAIL_VALUES:
            self.assertNotIn(v, r.stdout, "group key %r leaked in human mode" % v)


class ClientOutreachContractTest(unittest.TestCase):
    """client-outreach has no script; its PII / workspace-boundary guarantees are a PROSE
    contract in the SKILL.md. Asserted as contract-present and marked prose-only."""

    def setUp(self):
        p = os.path.join(ROOT, "skills", "client-outreach", "SKILL.md")
        with open(p, encoding="utf-8") as f:
            self.body = f.read()

    def test_outputs_stay_in_user_workspace_prose(self):
        # Outputs are written under the user's workspace (outreach/...), not the repo.
        self.assertIn("outreach/", self.body)

    def test_compliance_and_privacy_contract_present_prose(self):
        self.assertIn("PRIVACY.md", self.body)
        self.assertTrue(any(k in self.body for k in ("CAN-SPAM", "GDPR", "CASL")),
                        "outreach skill must state an anti-spam compliance contract")


def _rmtree(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
