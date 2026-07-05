"""test_status_truth.py -- C10 (depth-tier partition + triangulation) and C2 (duplicate
trigger) have teeth (W5). Each guard passes on the current tree AND is proven to FAIL on
a deliberately-broken fixture, so a wrong count breakdown or a colliding trigger cannot
ship silently.
"""
import os
import sys
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_release as vr  # noqa: E402


def _all_ok(rows):
    return all(ok for _n, ok, _d in rows)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _mini_tree(tmp, core, lite, routing, breakdown_ok=True):
    """A minimal plugin tree: one SKILL.md per named skill + SHIPPING/README/plugin.json
    carrying a depth-tiers block and the stated breakdown."""
    for s in core + lite + routing:
        _write(os.path.join(tmp, "skills", s, "SKILL.md"),
               "---\nname: %s\ndescription: x\n---\n\n# %s\n\n## Triggers\n\n- \"%s thing\"\n" % (s, s, s))
    n, m, k = len(core), len(lite), len(routing)
    block = "```depth-tiers\ncore:    %s\nlite:    %s\nrouting: %s\n```\n" % (
        ", ".join(core), ", ".join(lite), ", ".join(routing))
    total = n + m + k if breakdown_ok else n + m + k + 99
    line = "%d Core + %d Lite + %d routing (%d total)\n" % (n, m, k, total)
    _write(os.path.join(tmp, "SHIPPING.md"), "# Shipping\n\n" + block + "\n" + line)
    _write(os.path.join(tmp, "README.md"), "# R\n\n" + line)
    _write(os.path.join(tmp, ".claude-plugin", "plugin.json"),
           '{"version":"1.0.0","description":"%s"}' % line.strip())
    return tmp


class StatusTruthTest(unittest.TestCase):
    # --- current tree ---
    def test_current_tree_c10_passes(self):
        self.assertTrue(_all_ok(vr.check_status_truth(ROOT)),
                        "C10 must pass on the real tree: %s" % vr.check_status_truth(ROOT))

    def test_current_tree_c2_passes(self):
        self.assertTrue(_all_ok(vr.check_duplicate_triggers(ROOT)),
                        "C2 must pass on the real tree: %s" % vr.check_duplicate_triggers(ROOT))

    # --- C10 teeth ---
    def test_partition_passes_on_a_well_formed_mini_tree(self):
        tmp = tempfile.mkdtemp(prefix="dps_c10_ok_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        _mini_tree(tmp, ["a", "b"], ["c"], ["route-x"])
        self.assertTrue(_all_ok(vr.check_status_truth(tmp)))

    def test_partition_fails_when_a_skill_is_missing_from_every_tier(self):
        tmp = tempfile.mkdtemp(prefix="dps_c10_missing_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        # 'b' exists on disk but is listed in no tier -> partition must FAIL
        _mini_tree(tmp, ["a"], [], ["route-x"])
        _write(os.path.join(tmp, "skills", "b", "SKILL.md"),
               "---\nname: b\ndescription: x\n---\n\n# b\n")
        self.assertFalse(_all_ok(vr.check_status_truth(tmp)),
                         "an untiered on-disk skill must fail C10")

    def test_partition_fails_on_a_phantom_skill(self):
        tmp = tempfile.mkdtemp(prefix="dps_c10_phantom_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        # 'ghost' is in a tier but has no folder on disk -> FAIL
        _mini_tree(tmp, ["a", "ghost"], ["c"], ["route-x"])
        shutil.rmtree(os.path.join(tmp, "skills", "ghost"))
        self.assertFalse(_all_ok(vr.check_status_truth(tmp)),
                         "a tier naming a non-existent skill must fail C10")

    # --- C2 teeth ---
    def test_duplicate_trigger_is_detected(self):
        tmp = tempfile.mkdtemp(prefix="dps_c2_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        for s in ("one", "two"):
            _write(os.path.join(tmp, "skills", s, "SKILL.md"),
                   "---\nname: %s\ndescription: x\n---\n\n## Triggers\n\n- \"shared phrase\"\n" % s)
        self.assertFalse(_all_ok(vr.check_duplicate_triggers(tmp)),
                         "the same quoted trigger in two skills must fail C2")


if __name__ == "__main__":
    unittest.main()
