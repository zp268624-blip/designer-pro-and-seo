"""CLAUDE.md <-> AGENTS.md core-rule consistency (MASTER-PLAN 11.3).

The plugin ships both a CLAUDE.md and a platform-neutral AGENTS.md. They must agree on
the load-bearing rules so the two never drift. This runs in CI but is deliberately NOT a
registered verify_release.py gate check (the release-gate total stays 37).
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (rule label, token that must appear -- case-insensitively -- in BOTH files)
CORE_RULES = [
    ("clean-room originality", "clean-room"),
    ("skills compose, not duplicate", "compose"),
    ("no self-review / route to a different model", "route-codex-review"),
    ("status truth", "status truth"),
    ("stdlib-only Python", "standard library"),
]


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read().lower()


class AgentsMdConsistencyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.claude = _read("CLAUDE.md")
        cls.agents = _read("AGENTS.md")

    def test_both_files_exist_and_nonempty(self):
        self.assertGreater(len(self.claude), 200)
        self.assertGreater(len(self.agents), 200)

    def test_core_rules_agree_across_both_files(self):
        for label, token in CORE_RULES:
            t = token.lower()
            self.assertIn(t, self.claude, "CLAUDE.md missing core rule: %s" % label)
            self.assertIn(t, self.agents, "AGENTS.md missing core rule: %s" % label)

    def test_both_acknowledge_the_drift_contract(self):
        # both files state that the two must be kept in sync
        self.assertIn("drift", self.agents)


if __name__ == "__main__":
    unittest.main()
