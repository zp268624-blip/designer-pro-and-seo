"""C4 (connector Tier-2 present + script-exists + golden-example) tests.

Proves the three real connector skills (seo-geo, seo-sitemap, seo-technical) pass C4 on the
real tree, and that each planted RED fixture trips exactly its own row: a skill whose
capability-routing block declares an empty Tier-2, a skill whose Tier-2 names a script that
does not resolve on disk, and a skill whose Tier-2 script resolves but is not exercised by a
golden example under references/examples/<skill>/.
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_release as vr  # noqa: E402

# The W2 connector trio plus the Wave-3 flagships that have earned a machine-parseable
# capability-routing block (seo-cluster: serp-keywords Tier-2 via serp_cluster.py;
# design-accessibility: structural-a11y Tier-2 via a11y_static.py).
EXPECTED_BLOCK_SKILLS = {"seo-geo", "seo-sitemap", "seo-technical", "seo-cluster",
                         "seo-local-unified", "design-accessibility"}


def _find(rows, needle):
    for name, ok, detail in rows:
        if needle in name:
            return ok, detail
    raise AssertionError("no row matching %r in %r" % (needle, [r[0] for r in rows]))


def _skill_md(name, tier2):
    return (
        "# %s\n\n## Steps\n\nRun the method.\n\n"
        "## Capability routing\n\nCascade prose.\n\n"
        "```capability-routing\n"
        "capability:   site-map\n"
        "tier1:        none\n"
        "tier1_signal: none\n"
        "tier2:        %s\n"
        "tier2_yields: a real free deliverable\n"
        "tier3:        none\n"
        "tier3_signal: none\n"
        "tier4:        manual checklist\n"
        "needs_tier1:  none\n"
        "```\n\n## Outputs\n\nx\n" % (name, tier2)
    )


class Tier2Tree(unittest.TestCase):
    def _tree(self):
        tmp = tempfile.mkdtemp(prefix="dps_c4_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        return tmp

    def _skill(self, root, name, tier2):
        d = os.path.join(root, "skills", name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(_skill_md(name, tier2))

    def _script(self, root, relpath):
        p = os.path.join(root, *relpath.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write("# stub\n")

    def _example(self, root, name, mentions):
        """Golden example that actually INVOKES the script (a runnable command), not a
        bare prose mention -- this is what the strict C4 (FIX 2) now requires."""
        d = os.path.join(root, "references", "examples", name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as f:
            f.write("## Command\n\n```\npython3 scripts/seo/%s "
                    "--file sample.html --no-network\n```\n" % mentions)

    def _example_prose(self, root, name, mentions):
        """Golden that only NAMES the script in prose -- no runnable command. Must FAIL C4."""
        d = os.path.join(root, "references", "examples", name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as f:
            f.write("This golden names `%s` in prose but runs no command.\n" % mentions)


class RealTreeTest(Tier2Tree):
    def test_three_real_connector_skills_pass_c4(self):
        for name, ok, detail in vr.check_tier2_present(ROOT):
            self.assertTrue(ok, "%s -- %s" % (name, detail))

    def test_exactly_the_three_expected_skills_carry_a_routing_block(self):
        # guards against the check passing vacuously: the 3 connector skills really do
        # embed a machine-parseable capability-routing block.
        have = set()
        for sf in vr.skill_files(ROOT):
            if vr._capability_routing_kvs(vr.read(sf)):
                have.add(os.path.basename(os.path.dirname(sf)))
        self.assertEqual(have, EXPECTED_BLOCK_SKILLS, "routing-block skill set drifted: %s" % sorted(have))


class EmptyTier2Test(Tier2Tree):
    def test_empty_tier2_trips_c4_nonempty(self):
        root = self._tree()
        self._skill(root, "seo-empty", "none")  # explicit empty Tier-2
        ok, detail = _find(vr.check_tier2_present(root), "non-empty Tier-2")
        self.assertFalse(ok, "tier2=none must FAIL C4 non-empty; detail=%s" % detail)
        self.assertIn("seo-empty", detail)
        # the script-resolve and golden-example rows are unaffected (we short-circuit on empty)
        self.assertTrue(_find(vr.check_tier2_present(root), "resolves on disk")[0])


class MissingScriptTest(Tier2Tree):
    def test_tier2_naming_a_nonexistent_script_trips_c4_resolve(self):
        root = self._tree()
        self._skill(root, "seo-ghost", "ghost_tool.py (does not exist on disk)")
        ok, detail = _find(vr.check_tier2_present(root), "resolves on disk")
        self.assertFalse(ok, "a non-resolving Tier-2 script must FAIL C4; detail=%s" % detail)
        self.assertIn("seo-ghost", detail)
        self.assertTrue(_find(vr.check_tier2_present(root), "non-empty Tier-2")[0])


class MissingExampleTest(Tier2Tree):
    def test_resolving_script_without_a_golden_example_trips_c4_example(self):
        root = self._tree()
        self._script(root, "scripts/seo/real_tool.py")
        self._skill(root, "seo-noex", "real_tool.py (resolves, but no example exercises it)")
        ok, detail = _find(vr.check_tier2_present(root), "golden example")
        self.assertFalse(ok, "a resolving Tier-2 with no golden example must FAIL C4; detail=%s" % detail)
        self.assertIn("seo-noex", detail)

    def test_resolving_script_with_a_golden_example_passes(self):
        root = self._tree()
        self._script(root, "scripts/seo/real_tool.py")
        self._skill(root, "seo-ok", "real_tool.py (resolves and is exercised)")
        self._example(root, "seo-ok", "real_tool.py")
        for name, ok, detail in vr.check_tier2_present(root):
            self.assertTrue(ok, "%s -- %s" % (name, detail))


class ProseMentionTest(Tier2Tree):
    """FIX 2 (C4): a golden that merely NAMES the Tier-2 script (no runnable command) must
    FAIL -- a bare basename mention no longer counts as 'exercised'."""

    def test_bare_prose_mention_without_command_trips_c4(self):
        root = self._tree()
        self._script(root, "scripts/seo/real_tool.py")
        self._skill(root, "seo-prose", "real_tool.py (named in prose, never invoked)")
        self._example_prose(root, "seo-prose", "real_tool.py")
        ok, detail = _find(vr.check_tier2_present(root), "golden example")
        self.assertFalse(ok, "a golden that only names the script must FAIL C4; detail=%s" % detail)
        self.assertIn("seo-prose", detail)

    def test_every_named_tier2_script_must_be_invoked(self):
        # two Tier-2 scripts; only one is invoked -> C4 must flag the un-invoked one.
        root = self._tree()
        self._script(root, "scripts/seo/tool_a.py")
        self._script(root, "scripts/seo/tool_b.py")
        self._skill(root, "seo-two", "tool_a.py (validate) + tool_b.py (discover)")
        self._example(root, "seo-two", "tool_a.py")  # invokes tool_a only
        ok, detail = _find(vr.check_tier2_present(root), "golden example")
        self.assertFalse(ok, "an un-invoked second Tier-2 script must FAIL C4; detail=%s" % detail)
        self.assertIn("tool_b.py", detail)


if __name__ == "__main__":
    unittest.main()
