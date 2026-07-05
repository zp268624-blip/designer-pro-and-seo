"""W3b DESIGN flagship-depth acceptance tests -- design-research lane.

Pins the design-research competitor-scoring rubric (`data/competitor-rubric.csv`)
plus its two earned references and the scored Outputs / Error Handling tables added
to `skills/design-research/SKILL.md`.

The rubric CSV must:
  - exist under data/ with a stable 7-column schema DERIVED from what a
    design-research scoring pass consumes (not any external schema),
  - carry a data-row count clear of every recorded `.cleanroom-thirdparty` +/-2
    band (C-COUNT) and clear of a column near-match,
  - carry a PROVENANCE row.
Each reference must exist under references/design-research/, be CITED by its exact
path inside the SKILL.md (C1 resolve), stay lean (<~200 lines, knowledge-not-steps:
no '## Steps' heading), and carry a PROVENANCE method-note row.
The deepened SKILL.md must carry a scored '## Outputs' table and an '## Error
Handling' table in canonical order (Outputs before Error Handling before
Dependencies before Notes).
"""
import csv
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKILL = "design-research"
RUBRIC_CSV = "data/competitor-rubric.csv"
REFS = [
    "references/design-research/competitor-rubric.md",
    "references/design-research/white-space-method.md",
]
EXPECTED_COLUMNS = [
    "dimension", "category", "weight", "what_good_looks_like",
    "what_bad_looks_like", "signal_to_check", "white_space_test",
]


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def _csv_shape(*parts):
    with open(os.path.join(ROOT, *parts), newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    cols = [c.strip() for c in (rows[0] if rows else [])]
    return max(0, len(rows) - 1), cols, rows


class RubricCsvTest(unittest.TestCase):
    def test_csv_exists_with_expected_schema(self):
        n, cols, _rows = _csv_shape(*RUBRIC_CSV.split("/"))
        self.assertEqual(cols, EXPECTED_COLUMNS,
                         "competitor-rubric.csv header must be the derived schema")
        self.assertGreater(n, 0, "competitor-rubric.csv has no data rows")

    def test_row_count_clears_inspiration_bands(self):
        # Every recorded inspiration on-disk count (smallest is 25); a rubric well
        # below that floor clears every +/-2 band with margin.
        n, _cols, _rows = _csv_shape(*RUBRIC_CSV.split("/"))
        self.assertEqual(n, 18, "row count is pinned at 18 (clear of every +/-2 band)")

    def test_every_row_is_well_formed(self):
        _n, cols, rows = _csv_shape(*RUBRIC_CSV.split("/"))
        cat = set()
        for r in rows[1:]:
            self.assertEqual(len(r), len(cols), "ragged row: %r" % (r,))
            # weight is an integer contribution to the composite score
            self.assertRegex(r[2].strip(), r"^\d+$", "weight not an int: %r" % (r,))
            cat.add(r[1].strip())
            for cell in r:
                self.assertNotIn(",", cell, "cells stay comma-free: %r" % (cell,))
        self.assertGreaterEqual(len(cat), 4, "rubric should span multiple categories")

    def test_csv_has_provenance_row(self):
        prov = _read("references", "PROVENANCE.md")
        self.assertIn("`competitor-rubric.csv`", prov,
                      "no PROVENANCE row for competitor-rubric.csv")


class RubricRefsTest(unittest.TestCase):
    def test_reference_files_exist_and_are_lean(self):
        for ref in REFS:
            p = os.path.join(ROOT, *ref.split("/"))
            self.assertTrue(os.path.exists(p), "missing reference: %s" % ref)
            n = len(_read(*ref.split("/")).splitlines())
            self.assertLessEqual(n, 210, "%s is %d lines (>~200)" % (ref, n))

    def test_reference_is_knowledge_not_steps(self):
        for ref in REFS:
            body = _read(*ref.split("/"))
            self.assertNotRegex(
                body, r"(?m)^##\s+Steps\b",
                "%s reads as procedure (has a '## Steps' heading)" % ref)

    def test_reference_cited_by_exact_path_in_skill(self):
        body = _read("skills", SKILL, "SKILL.md")
        for ref in REFS:
            self.assertIn(ref, body,
                          "%s does not cite %s by exact path" % (SKILL, ref))

    def test_reference_has_provenance_row(self):
        prov = _read("references", "PROVENANCE.md")
        for ref in REFS:
            self.assertIn("`%s`" % ref, prov,
                          "no PROVENANCE method-note row for %s" % ref)


class DeepenedSkillTest(unittest.TestCase):
    def test_scored_outputs_and_error_tables(self):
        body = _read("skills", SKILL, "SKILL.md")
        self.assertRegex(body, r"(?m)^##\s+Outputs\b", "missing '## Outputs'")
        self.assertRegex(body, r"(?m)^##\s+Error Handling\b",
                         "missing '## Error Handling'")
        for heading in ("Outputs", "Error Handling"):
            seg = body.split("## %s" % heading, 1)[1]
            seg = re.split(r"(?m)^##\s+", seg, 1)[0]
            self.assertIn("|", seg, "'%s' has no table" % heading)
            self.assertRegex(
                seg, r"(?m)^\s*\|[\s:|-]+\|\s*$",
                "'%s' table has no delimiter row" % heading)

    def test_canonical_order(self):
        body = _read("skills", SKILL, "SKILL.md")
        o = body.index("## Outputs")
        e = body.index("## Error Handling")
        d = body.index("## Dependencies")
        n = body.index("## Notes")
        self.assertLess(o, e, "Outputs must precede Error Handling")
        self.assertLess(e, d, "Error Handling must precede Dependencies")
        self.assertLess(d, n, "Dependencies must precede Notes")


if __name__ == "__main__":
    unittest.main()
