"""C-HANDOFF tests: the three named handoffs pinned against the CURRENT tree, plus a
planted-edge negative test that proves the guard trips when severance is attempted.
"""
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_release as vr  # noqa: E402

HANDOFF_SKILLS = ["qa-gate", "design-research", "seo-drift", "design-visual-qa"]


def _find(rows, needle):
    for name, ok, detail in rows:
        if needle in name:
            return ok, detail
    raise AssertionError("no row matching %r in %r" % (needle, [r[0] for r in rows]))


class HandoffTest(unittest.TestCase):
    def test_current_tree_all_handoffs_hold(self):
        for name, ok, detail in vr.check_handoffs(ROOT):
            self.assertTrue(ok, "%s -- %s" % (name, detail))

    def test_planted_dependency_edge_fails(self):
        tmp = tempfile.mkdtemp(prefix="dps_handoff_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        # copy the four real handoff skills into the temp tree
        for s in HANDOFF_SKILLS:
            src = os.path.join(ROOT, "skills", s, "SKILL.md")
            dst_dir = os.path.join(tmp, "skills", s)
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copyfile(src, os.path.join(dst_dir, "SKILL.md"))

        # plant a forbidden Dependencies edge: list seo-drift under design-visual-qa's
        # ## Dependencies (the exact severance C-HANDOFF must catch)
        vq = os.path.join(tmp, "skills", "design-visual-qa", "SKILL.md")
        with open(vq, encoding="utf-8") as f:
            body = f.read()
        body = re.sub(r"(?m)^(## Dependencies\s*\n)",
                      r"\1\n- `seo-drift` (planted forbidden edge)\n", body, count=1)
        with open(vq, "w", encoding="utf-8") as f:
            f.write(body)

        rows = vr.check_handoffs(tmp)
        edge_ok, edge_detail = _find(rows, "NOT a Dependencies edge")
        self.assertFalse(edge_ok, "planted edge should trip C-HANDOFF; detail=%s" % edge_detail)
        # the orchestrator-side handoffs and the Notes-level mutual reference still hold
        self.assertTrue(_find(rows, "qa-gate -> seo-page")[0])
        self.assertTrue(_find(rows, "design-research -> seo-cluster")[0])
        self.assertTrue(_find(rows, "Notes-level mutual reference")[0])

    def test_severed_dependency_with_lingering_prose_fails(self):
        # FIX 10: prove SEVERANCE is detected, not just a forbidden-edge addition. Remove the
        # required orchestrator->specialist edges (qa-gate->seo-page, design-research->
        # seo-cluster) from the ## Dependencies section but LEAVE a prose mention of the
        # skill. A raw-substring check would falsely pass; the real-entry parser must FAIL.
        tmp = tempfile.mkdtemp(prefix="dps_handoff_sever_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        for s in HANDOFF_SKILLS:
            src = os.path.join(ROOT, "skills", s, "SKILL.md")
            dst_dir = os.path.join(tmp, "skills", s)
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copyfile(src, os.path.join(dst_dir, "SKILL.md"))

        def _sever(skill, skill_id):
            p = os.path.join(tmp, "skills", skill, "SKILL.md")
            with open(p, encoding="utf-8") as f:
                body = f.read()
            # replace the backticked bullet ENTRY with a non-bullet prose line that still
            # names the skill (the exact "lingering prose mention" severance)
            new_body, n = re.subn(r"(?m)^- `%s`.*$" % re.escape(skill_id),
                                  "This phase no longer depends on %s (now inlined)." % skill_id,
                                  body, count=1)
            self.assertEqual(n, 1, "expected to find the `%s` bullet to sever" % skill_id)
            with open(p, "w", encoding="utf-8") as f:
                f.write(new_body)

        _sever("qa-gate", "seo-page")
        _sever("design-research", "seo-cluster")

        rows = vr.check_handoffs(tmp)
        qa_ok, qa_detail = _find(rows, "qa-gate -> seo-page")
        self.assertFalse(qa_ok, "severed qa-gate->seo-page edge must FAIL; detail=%s" % qa_detail)
        dr_ok, dr_detail = _find(rows, "design-research -> seo-cluster")
        self.assertFalse(dr_ok, "severed design-research->seo-cluster edge must FAIL; detail=%s" % dr_detail)
        # the untouched relationships still hold
        self.assertTrue(_find(rows, "NOT a Dependencies edge")[0])
        self.assertTrue(_find(rows, "Notes-level mutual reference")[0])

    def _qa_gate_tree(self, deps_body):
        """Build a throwaway tree with only skills/qa-gate/SKILL.md, whose ## Dependencies
        section body is `deps_body`. The other handoff skills are absent (check_handoffs
        treats a missing file as an empty deps set)."""
        tmp = tempfile.mkdtemp(prefix="dps_handoff_dep_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        d = os.path.join(tmp, "skills", "qa-gate")
        os.makedirs(d)
        with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("# qa-gate\n\n## Dependencies\n\n" + deps_body + "\n\n## Notes\n\nx\n")
        return tmp

    def test_mid_sentence_backtick_does_not_satisfy_edge(self):
        # FIX C (RED): a backticked id embedded mid-sentence ('not a dependency on `seo-page`')
        # is NOT a real entry, so the qa-gate->seo-page edge must FAIL.
        tmp = self._qa_gate_tree("- not a dependency on `seo-page`")
        ok, detail = _find(vr.check_handoffs(tmp), "qa-gate -> seo-page")
        self.assertFalse(ok, "mid-sentence `seo-page` must NOT satisfy the edge; detail=%s" % detail)

    def test_leading_backtick_entry_satisfies_edge(self):
        # FIX C (GREEN): a proper `- `seo-page` — reason` bullet IS a real entry and PASSES.
        tmp = self._qa_gate_tree("- `seo-page` — adds full on-page SEO pass")
        ok, detail = _find(vr.check_handoffs(tmp), "qa-gate -> seo-page")
        self.assertTrue(ok, "a proper leading `- `seo-page`` bullet must satisfy the edge; detail=%s" % detail)


if __name__ == "__main__":
    unittest.main()
