"""C1 reference-resolution tests.

A SKILL.md that cites references/<x>.md must resolve to a real file on disk. Verifies the
current tree is clean, that an orphan citation in a temp root is caught RED, and that a
resolvable citation passes GREEN.
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_release as vr  # noqa: E402


class RefsResolveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dps_c1_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _skill(self, name, body):
        d = os.path.join(self.tmp, "skills", name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(body)

    def _ref(self, relpath, body="x"):
        p = os.path.join(self.tmp, *relpath.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)

    def _row(self):
        rows = vr.check_skill_ref_resolve(self.tmp)
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_orphan_reference_is_caught(self):
        self._skill("seo-x", "See `references/does-not-exist.md` for detail.\n")
        _, ok, detail = self._row()
        self.assertFalse(ok, "orphan reference should FAIL; detail=%s" % detail)
        self.assertIn("does-not-exist.md", detail)

    def test_resolvable_reference_passes(self):
        self._ref("references/real-depth.md")
        self._skill("seo-x", "Load `references/real-depth.md` on demand.\n")
        _, ok, detail = self._row()
        self.assertTrue(ok, "resolvable reference should PASS; detail=%s" % detail)

    def test_nested_shared_reference_resolves(self):
        self._ref("references/shared/cwv.md")
        self._skill("seo-y", "Thresholds in `references/shared/cwv.md`.\n")
        _, ok, detail = self._row()
        self.assertTrue(ok, detail)

    def test_current_tree_references_all_resolve(self):
        _, ok, detail = vr.check_skill_ref_resolve(ROOT)[0]
        self.assertTrue(ok, "real tree has a broken reference: %s" % detail)


if __name__ == "__main__":
    unittest.main()
