"""Tests for scripts/workflow/capability_probe.py -- the capability/tier probe a
skill runs to decide Tier 3/4 routing and to name what to install.

Contract under test (the parts this task adds, plus the invariants it must keep):
  - DEFAULT JSON output always carries the "cli" key and the probe ALWAYS exits 0
    (availability is information, not failure) -- the smoke test depends on this.
  - The env view reports the NEW presence-only keys (MOZ_API_KEY,
    BING_WEBMASTER_API_KEY, CRUX_API_KEY, FIRECRAWL_API_URL) alongside the existing
    DATAFORSEO_*, FIRECRAWL_API_KEY, GEMINI_API_KEY, GOOGLE_API_KEY -- each as a
    BOOLEAN, and the secret VALUE is never leaked into stdout.
  - `--capabilities` emits a Tier-1 -> Tier-4 cascade view (one row per capability
    family from references/CAPABILITY-TIERS.md) and STILL carries "cli" + exits 0.
  - `--budget` is a passthrough: its value is recorded in the output, no behavior.

Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/`, no pip
install, no network (the probe only reads PATH + os.environ).
"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "workflow", "capability_probe.py")

# New presence-only env keys this task adds, plus the ones that must remain.
NEW_ENV_KEYS = ["MOZ_API_KEY", "BING_WEBMASTER_API_KEY", "CRUX_API_KEY", "FIRECRAWL_API_URL"]
EXISTING_ENV_KEYS = ["DATAFORSEO_USERNAME", "DATAFORSEO_PASSWORD",
                     "FIRECRAWL_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"]


def run(args, env=None):
    """Run the probe with a CLEAN env (so host secrets never perturb the test)."""
    base = {k: v for k, v in os.environ.items()
            if k not in (NEW_ENV_KEYS + EXISTING_ENV_KEYS)}
    if env:
        base.update(env)
    return subprocess.run([sys.executable, SCRIPT] + args,
                          capture_output=True, encoding="utf-8", env=base)


class DefaultContractTest(unittest.TestCase):
    def test_exits_zero_and_has_cli(self):
        r = run([])
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIn("cli", data)
        self.assertIsInstance(data["cli"], dict)

    def test_bad_arg_still_exits_zero_with_cli(self):
        # availability is information, not failure -- unknown args must not crash.
        r = run(["--definitely-not-a-flag"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("cli", json.loads(r.stdout))


class EnvKeysTest(unittest.TestCase):
    def test_new_and_existing_keys_present_as_booleans(self):
        data = json.loads(run([]).stdout)
        self.assertIn("env", data)
        for key in NEW_ENV_KEYS + EXISTING_ENV_KEYS:
            self.assertIn(key, data["env"], "missing env key: %s" % key)
            self.assertIsInstance(data["env"][key], bool,
                                  "%s must be a boolean, never the value" % key)

    def test_set_key_reports_true_without_leaking_value(self):
        secret = "SUPERSECRET-do-not-leak-123456"
        r = run([], env={"MOZ_API_KEY": secret})
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIs(data["env"]["MOZ_API_KEY"], True)
        self.assertNotIn(secret, r.stdout)

    def test_unset_key_reports_false(self):
        data = json.loads(run([]).stdout)
        self.assertIs(data["env"]["CRUX_API_KEY"], False)


class CapabilitiesViewTest(unittest.TestCase):
    def test_capabilities_emits_tier_view_and_keeps_cli(self):
        r = run(["--capabilities"])
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIn("cli", data)  # invariant must survive the new view
        self.assertIn("capabilities", data)
        caps = data["capabilities"]
        self.assertIsInstance(caps, list)
        self.assertTrue(caps)
        slugs = {c["capability"] for c in caps}
        for expected in ("serp-keywords", "backlinks", "cwv-field", "image-gen"):
            self.assertIn(expected, slugs)
        for c in caps:
            self.assertIn("active_tier", c)
            self.assertIn(c["active_tier"], ("tier1", "tier2", "tier3", "tier4"))
            for t in ("tier1", "tier2", "tier3", "tier4"):
                self.assertIn(t, c)

    def test_env_signal_promotes_to_tier1(self):
        # backlinks unlocks Tier 1 when MOZ_API_KEY is set.
        data = json.loads(run(["--capabilities"], env={"MOZ_API_KEY": "x"}).stdout)
        bl = next(c for c in data["capabilities"] if c["capability"] == "backlinks")
        self.assertTrue(bl["tier1"]["available"])
        self.assertEqual(bl["active_tier"], "tier1")

    def test_capabilities_human_is_ascii_and_exits_zero(self):
        r = run(["--capabilities", "--human"])
        self.assertEqual(r.returncode, 0, r.stderr)
        r.stdout.encode("ascii")  # raises if non-ASCII leaked


class BudgetPassthroughTest(unittest.TestCase):
    def test_budget_recorded_in_output(self):
        r = run(["--budget", "free"])
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data.get("budget"), "free")
        self.assertIn("cli", data)  # passthrough must not change behavior

    def test_budget_absent_is_null(self):
        data = json.loads(run([]).stdout)
        self.assertIsNone(data.get("budget"))


if __name__ == "__main__":
    unittest.main()
