"""C8 provenance coverage tests, run against the real plugin tree.

Asserts every references/shared/*.md and AGENTS.md is recorded in PROVENANCE, that each
shared file stays under the ~200-line knowledge-not-steps budget, and that the C8 gate
check itself is green on the current tree.
"""
import glob
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_release as vr  # noqa: E402

LINE_BUDGET = 200
SHARED = sorted(glob.glob(os.path.join(ROOT, "references", "shared", "*.md")))


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class ProvenanceTest(unittest.TestCase):
    def test_shared_dir_is_populated(self):
        self.assertTrue(SHARED, "expected references/shared/*.md to exist")

    def test_every_shared_ref_has_a_provenance_row(self):
        prov = _read(os.path.join(ROOT, "references", "PROVENANCE.md"))
        for sf in SHARED:
            relp = os.path.relpath(sf, ROOT).replace("\\", "/")
            self.assertIn(relp, prov, "no PROVENANCE row for %s" % relp)

    def test_agents_md_has_a_provenance_row(self):
        prov = _read(os.path.join(ROOT, "references", "PROVENANCE.md"))
        self.assertIn("AGENTS.md", prov)

    def test_shared_files_under_line_budget(self):
        for sf in SHARED:
            n = _read(sf).count("\n") + 1
            self.assertLessEqual(
                n, LINE_BUDGET,
                "%s is %d lines (> %d budget)" % (os.path.basename(sf), n, LINE_BUDGET))

    def test_high_risk_rows_carry_method_notes(self):
        # The same logic the gate enforces (C8): each shared-ref row carries an
        # (a)/(b)/(c) / "not open" / public-standard method note.
        prov = _read(os.path.join(ROOT, "references", "PROVENANCE.md"))
        import re
        for sf in SHARED:
            relp = os.path.relpath(sf, ROOT).replace("\\", "/")
            row = next((ln for ln in prov.splitlines() if relp in ln), "")
            self.assertTrue(row, "row missing for %s" % relp)
            self.assertTrue(
                re.search(r"\(a\)|not open|first principles|PUBLIC", row, re.I),
                "no clean-room method note on the row for %s" % relp)

    def test_c8_gate_check_passes_on_current_tree(self):
        for name, ok, detail in vr.check_prov_classes(ROOT):
            self.assertTrue(ok, "%s -- %s" % (name, detail))

    def test_every_skill_cited_reference_has_a_provenance_row(self):
        # C8 prong 2, asserted directly against the real tree: every references/**/*.md a
        # SKILL.md points at (per-skill references included) is recorded in PROVENANCE.
        prov = _read(os.path.join(ROOT, "references", "PROVENANCE.md"))
        for ref in vr._cited_references(ROOT):
            self.assertIsNotNone(vr._prov_row_line(prov, ref),
                                 "no PROVENANCE row for SKILL-cited reference %s" % ref)


class C8CitedReferenceFixtureTest(unittest.TestCase):
    """RED fixture: a per-skill reference CITED by a SKILL.md but with NO PROVENANCE row
    must trip the hardened C8 check; backfilling a backtick row + method note clears it."""

    _CLASSES = ("Scripts", "CSV data", "Per-skill references", "Agents",
                "Templates & prompt-libraries", "Connector-wirings")

    def _build(self, td, prov_body):
        import os as _os
        _os.makedirs(_os.path.join(td, "references", "shared"))
        _os.makedirs(_os.path.join(td, "skills", "demo"))
        with open(_os.path.join(td, "references", "shared", "foo.md"), "w", encoding="utf-8") as f:
            f.write("# foo\nshared knowledge\n")
        with open(_os.path.join(td, "references", "PROVENANCE.md"), "w", encoding="utf-8") as f:
            f.write(prov_body)
        # a SKILL that CITES a per-skill reference (bar.md)
        with open(_os.path.join(td, "skills", "demo", "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("# demo skill\nSee references/demo/bar.md for the method.\n")

    def _prov_head(self):
        head = "# PROVENANCE\n\n" + "".join("## %s\n\n" % c for c in self._CLASSES)
        head += ("| Asset | class | check | note |\n|---|---|---|---|\n"
                 "| `references/shared/foo.md` | ref | original | (a) first principles; source NOT open |\n"
                 "| `AGENTS.md` | doc | original | (a) first principles |\n")
        return head

    def _rows(self, td):
        import tempfile  # noqa: F401
        return {name: (ok, detail) for name, ok, detail in vr.check_prov_classes(td)}

    KEY = "C8 prov: every SKILL-cited per-skill reference has a PROVENANCE row"

    def test_missing_row_trips_and_backfill_clears(self):
        import tempfile
        # 1) no row for the cited bar.md -> C8 fails, naming the culprit
        with tempfile.TemporaryDirectory() as td:
            self._build(td, self._prov_head())
            rows = self._rows(td)
            self.assertIn(self.KEY, rows)
            ok, detail = rows[self.KEY]
            self.assertFalse(ok, "a cited per-skill reference with no PROVENANCE row must trip C8")
            self.assertIn("references/demo/bar.md", detail)
        # 2) backfilling a first-cell backtick row + method note satisfies C8
        with tempfile.TemporaryDirectory() as td:
            prov = self._prov_head() + ("| `references/demo/bar.md` | per-skill ref | original |"
                                        " (a) first principles; source NOT open |\n")
            self._build(td, prov)
            self.assertTrue(self._rows(td)[self.KEY][0],
                            "a backtick row + method note must satisfy the hardened C8")


if __name__ == "__main__":
    unittest.main()
