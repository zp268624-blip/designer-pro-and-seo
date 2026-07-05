"""W3b DESIGN flagship-depth acceptance tests.

Pins the three earned design references + the scored Outputs / Error Handling tables
added to the three deepened design SKILL.md bodies. Each reference must:
  - exist on disk under references/<skill>/,
  - be CITED by its exact path inside its SKILL.md (C1 resolve),
  - stay lean (<~200 lines, knowledge-not-steps: no procedural '## Steps' heading),
  - carry a PROVENANCE method-note row.
Each deepened SKILL.md must carry a scored '## Outputs' table and an '## Error Handling'
table (per references/skill-section-template.md), in canonical order (Outputs before
Dependencies; Error Handling with Outputs).
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (skill, reference path relative to plugin root)
CASES = [
    ("design-system-gen", "references/design-system-gen/ranking.md"),
    ("design-build", "references/design-build/anti-slop.md"),
    ("design-visual-qa", "references/design-visual-qa/visual-qa-rubric.md"),
]


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class DesignFlagshipRefsTest(unittest.TestCase):
    def test_reference_files_exist_and_are_lean(self):
        for _skill, ref in CASES:
            p = os.path.join(ROOT, *ref.split("/"))
            self.assertTrue(os.path.exists(p), "missing reference: %s" % ref)
            n = len(_read(*ref.split("/")).splitlines())
            self.assertLessEqual(n, 210, "%s is %d lines (>~200)" % (ref, n))

    def test_reference_is_knowledge_not_steps(self):
        # a per-skill reference holds durable knowledge, not a '## Steps' procedure.
        for _skill, ref in CASES:
            body = _read(*ref.split("/"))
            self.assertNotRegex(
                body, r"(?m)^##\s+Steps\b",
                "%s reads as procedure (has a '## Steps' heading)" % ref)

    def test_reference_cited_by_exact_path_in_skill(self):
        for skill, ref in CASES:
            body = _read("skills", skill, "SKILL.md")
            self.assertIn(ref, body,
                          "%s does not cite %s by exact path" % (skill, ref))

    def test_reference_has_provenance_row(self):
        prov = _read("references", "PROVENANCE.md")
        for _skill, ref in CASES:
            self.assertIn("`%s`" % ref, prov,
                          "no PROVENANCE method-note row for %s" % ref)

    def test_deepened_skills_have_scored_outputs_and_error_tables(self):
        for skill, _ref in CASES:
            body = _read("skills", skill, "SKILL.md")
            self.assertRegex(body, r"(?m)^##\s+Outputs\b",
                             "%s missing '## Outputs'" % skill)
            self.assertRegex(body, r"(?m)^##\s+Error Handling\b",
                             "%s missing '## Error Handling'" % skill)
            # each new table must be a real markdown table (header + delimiter row)
            for heading in ("Outputs", "Error Handling"):
                seg = body.split("## %s" % heading, 1)[1]
                seg = re.split(r"(?m)^##\s+", seg, maxsplit=1)[0]
                self.assertIn("|", seg, "%s '%s' has no table" % (skill, heading))
                self.assertRegex(
                    seg, r"(?m)^\s*\|[\s:|-]+\|\s*$",
                    "%s '%s' table has no delimiter row" % (skill, heading))

    def test_canonical_order_outputs_before_dependencies(self):
        for skill, _ref in CASES:
            body = _read("skills", skill, "SKILL.md")
            o = body.index("## Outputs")
            e = body.index("## Error Handling")
            d = body.index("## Dependencies")
            n = body.index("## Notes")
            self.assertLess(o, e, "%s: Outputs must precede Error Handling" % skill)
            self.assertLess(e, d, "%s: Error Handling must precede Dependencies" % skill)
            self.assertLess(d, n, "%s: Dependencies must precede Notes" % skill)


if __name__ == "__main__":
    unittest.main()
