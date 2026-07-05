"""C3 (agent well-formedness + one-directional DAG + dispatch-shape) and C5 (agent
least-privilege) tests.

Proves the W2 proof agent (agents/seo-technical.md) passes both checks on the real tree,
and that each planted RED fixture in a temp tree trips exactly its own check: a malformed
agent (missing the ## Output contract block), a fetch-only agent that also holds Bash, an
agent that names an orchestrator as a Dependencies edge, and a fenced ```dispatch block
that mirrors a third-party 8-always + 7-conditional split.
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_release as vr  # noqa: E402


def _find(rows, needle):
    for name, ok, detail in rows:
        if needle in name:
            return ok, detail
    raise AssertionError("no row matching %r in %r" % (needle, [r[0] for r in rows]))


def _agent_md(name="seo-x", tools="Read, Glob, Grep, Bash, Write", deps=None,
              with_output=True, with_routing=True, drop_key=None,
              routing_block=True, output_block=True, routing_drop=None, output_drop=None):
    fm = [
        "---",
        "name: %s" % name,
        "description: Dispatched leaf for %s; wraps the %s skill method, no forked logic." % (name, name),
        "model: sonnet",
        "maxTurns: 12",
        "tools: %s" % tools,
        "---",
    ]
    if drop_key:  # remove a required frontmatter line to plant a malformed-frontmatter fixture
        fm = [ln for ln in fm if not ln.startswith(drop_key + ":")]
    parts = ["", "# %s  (dispatched-leaf agent)" % name, "",
             "**Wraps:** `skills/%s/SKILL.md` -- same method, no forked logic." % name, ""]
    if with_routing:
        # heading + prose; the fenced block (with all required keys) only when routing_block.
        parts += ["## Capability routing", "", "Obeys the plugin cascade; Tier 2 is the product.", ""]
        if routing_block:
            rb = [
                "```capability-routing",
                "capability:   cwv-field",
                "tier1:        none",
                "tier1_signal: none",
                "tier2:        tech_audit.py (lab audit)",
                "tier2_yields: findings",
                "tier3:        none",
                "tier3_signal: none",
                "tier4:        manual checklist",
                "needs_tier1:  none",
                "```", "",
            ]
            if routing_drop:  # drop a single required key to plant a missing-key fixture
                rb = [ln for ln in rb if not ln.startswith(routing_drop + ":")]
            parts += rb
    if with_output:
        parts += ["## Output contract", "", "Returns the fixed machine-parseable block.", ""]
        if output_block:
            ob = [
                "```output-contract",
                "agent:       %s" % name,
                "status:      ok | partial | error",
                "tier_ran:    1 | 2 | 4",
                "needs_tier1: none",
                "tier_line:   tier 2 ran; a connector would add field data",
                "```", "",
            ]
            if output_drop:
                ob = [ln for ln in ob if not ln.startswith(output_drop + ":")]
            parts += ob
    if deps:
        parts += ["## Dependencies", ""] + ["- `%s` -- planted" % d for d in deps] + [""]
    return "\n".join(fm + parts)


class AgentTree(unittest.TestCase):
    def _tree(self):
        tmp = tempfile.mkdtemp(prefix="dps_agents_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        return tmp

    def _write_agent(self, root, name, **kw):
        d = os.path.join(root, "agents")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "%s.md" % name), "w", encoding="utf-8") as f:
            f.write(_agent_md(name=name, **kw))


class ProofAgentTest(AgentTree):
    def test_proof_agent_passes_c3_on_real_tree(self):
        for name, ok, detail in vr.check_agent_wellformed(ROOT):
            self.assertTrue(ok, "%s -- %s" % (name, detail))

    def test_proof_agent_passes_c5_on_real_tree(self):
        for name, ok, detail in vr.check_agent_least_privilege(ROOT):
            self.assertTrue(ok, "%s -- %s" % (name, detail))

    def test_a_clean_planted_agent_passes_both(self):
        root = self._tree()
        self._write_agent(root, "seo-clean")
        for name, ok, detail in vr.check_agent_wellformed(root) + vr.check_agent_least_privilege(root):
            self.assertTrue(ok, "%s -- %s" % (name, detail))


class MalformedAgentTest(AgentTree):
    def test_missing_output_contract_trips_c3_wellformedness(self):
        root = self._tree()
        self._write_agent(root, "seo-orphan", with_output=False)
        ok, detail = _find(vr.check_agent_wellformed(root), "Capability routing + a ## Output")
        self.assertFalse(ok, "agent missing ## Output contract must FAIL C3; detail=%s" % detail)
        self.assertIn("seo-orphan", detail)
        # the other C3 rows are unaffected
        self.assertTrue(_find(vr.check_agent_wellformed(root), "dispatch-shape")[0])

    def test_missing_frontmatter_key_trips_c5_required_keys(self):
        root = self._tree()
        self._write_agent(root, "seo-nokey", drop_key="model")
        ok, detail = _find(vr.check_agent_least_privilege(root), "required frontmatter keys")
        self.assertFalse(ok, "agent missing 'model' must FAIL C5 required-keys; detail=%s" % detail)
        self.assertIn("model", detail)


class LeastPrivilegeTest(AgentTree):
    def test_fetch_only_agent_holding_bash_trips_c5(self):
        root = self._tree()
        self._write_agent(root, "seo-fetcher", tools="Read, Glob, WebFetch, Bash")
        ok, detail = _find(vr.check_agent_least_privilege(root), "holds Bash")
        self.assertFalse(ok, "WebFetch + Bash must FAIL C5 least-privilege; detail=%s" % detail)
        self.assertIn("seo-fetcher", detail)

    def test_task_tool_trips_overprivilege_and_agent_call(self):
        root = self._tree()
        self._write_agent(root, "seo-dispatcher", tools="Read, Task")
        over_ok, over_detail = _find(vr.check_agent_least_privilege(root), "high-privilege tool")
        self.assertFalse(over_ok, "Task grant must FAIL C5 over-privilege; detail=%s" % over_detail)
        call_ok, call_detail = _find(vr.check_agent_wellformed(root), "calls another agent")
        self.assertFalse(call_ok, "holding Task must FAIL the C3 agent->agent edge guard; detail=%s" % call_detail)


class OrchestratorDepTest(AgentTree):
    def test_agent_listing_orchestrator_dependency_trips_c3(self):
        root = self._tree()
        self._write_agent(root, "seo-leaf", deps=["seo-audit"])
        ok, detail = _find(vr.check_agent_wellformed(root), "orchestrator as a Dependencies")
        self.assertFalse(ok, "naming the seo-audit orchestrator as a dep must FAIL C3; detail=%s" % detail)
        self.assertIn("seo-audit", detail)


class FencedBlockContentTest(AgentTree):
    """FIX 1 (C3): the well-formedness row validates fenced-block CONTENT, not just the
    headings. A heading with no fenced block, or a fenced block missing a required key,
    must FAIL -- not pass vacuously."""

    def test_capability_heading_without_fenced_block_trips_c3(self):
        root = self._tree()
        self._write_agent(root, "seo-noroutblk", routing_block=False)  # heading present, no block
        ok, detail = _find(vr.check_agent_wellformed(root), "Capability routing + a ## Output")
        self.assertFalse(ok, "a ## Capability routing heading with no fenced block must FAIL C3; detail=%s" % detail)
        self.assertIn("seo-noroutblk", detail)

    def test_capability_block_missing_any_required_key_trips_c3(self):
        # Full coverage: dropping ANY of the routing block's required keys (incl.
        # tier3_signal) must FAIL C3 -- not just tier2.
        for key in vr.CAPABILITY_ROUTING_KEYS:
            root = self._tree()
            self._write_agent(root, "seo-misskey", routing_drop=key)
            ok, detail = _find(vr.check_agent_wellformed(root), "Capability routing + a ## Output")
            self.assertFalse(ok, "a capability-routing block missing '%s' must FAIL C3; detail=%s" % (key, detail))
            self.assertIn("seo-misskey", detail)

    def test_output_heading_without_fenced_block_trips_c3(self):
        root = self._tree()
        self._write_agent(root, "seo-nooutblk", output_block=False)  # heading present, no block
        ok, detail = _find(vr.check_agent_wellformed(root), "Capability routing + a ## Output")
        self.assertFalse(ok, "a ## Output contract heading with no fenced block must FAIL C3; detail=%s" % detail)
        self.assertIn("seo-nooutblk", detail)

    def test_output_block_missing_any_required_key_trips_c3(self):
        # Full missing-key coverage: dropping ANY of the five universal required keys
        # (agent/status/tier_ran/needs_tier1/tier_line) must FAIL C3 -- not just status.
        for key in vr.OUTPUT_CONTRACT_KEYS:
            root = self._tree()
            self._write_agent(root, "seo-outmiss", output_drop=key)
            ok, detail = _find(vr.check_agent_wellformed(root), "Capability routing + a ## Output")
            self.assertFalse(ok, "an output-contract block missing '%s' must FAIL C3; detail=%s" % (key, detail))
            self.assertIn("seo-outmiss", detail)


class AgentParityTest(AgentTree):
    """FIX 3 (C3 parity): name<->file<->sibling-skill parity. An orphan agent (no sibling
    skill) or a name!=filename mismatch must FAIL; a paired agent passes."""

    def _write_skill(self, root, name):
        d = os.path.join(root, "skills", name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("# %s\n\nSibling skill stub.\n" % name)

    def test_proof_agent_passes_parity_on_real_tree(self):
        for name, ok, detail in vr.check_agent_parity(ROOT):
            self.assertTrue(ok, "%s -- %s" % (name, detail))

    def test_orphan_agent_without_sibling_skill_trips_parity(self):
        root = self._tree()
        self._write_agent(root, "seo-orphanx")  # no skills/seo-orphanx/SKILL.md
        ok, detail = _find(vr.check_agent_parity(root), "sibling skill")
        self.assertFalse(ok, "an orphan agent (no sibling skill) must FAIL parity; detail=%s" % detail)
        self.assertIn("seo-orphanx", detail)
        # the name<->filename row is unaffected (name == filename here)
        self.assertTrue(_find(vr.check_agent_parity(root), "frontmatter name matches")[0])

    def test_name_filename_mismatch_trips_parity(self):
        root = self._tree()
        d = os.path.join(root, "agents")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "seo-named.md"), "w", encoding="utf-8") as f:
            f.write(_agent_md(name="seo-other"))  # frontmatter name != filename stem
        self._write_skill(root, "seo-named")  # sibling exists so only the name row trips
        ok, detail = _find(vr.check_agent_parity(root), "frontmatter name matches")
        self.assertFalse(ok, "frontmatter name != filename must FAIL parity; detail=%s" % detail)
        self.assertIn("seo-named", detail)

    def test_paired_agent_with_sibling_skill_passes_parity(self):
        root = self._tree()
        self._write_agent(root, "seo-paired")
        self._write_skill(root, "seo-paired")
        for name, ok, detail in vr.check_agent_parity(root):
            self.assertTrue(ok, "%s -- %s" % (name, detail))


class DispatchShapeTest(AgentTree):
    def _orchestrator_with_split(self, root, always_n, conditional_n):
        d = os.path.join(root, "skills", "seo-audit")
        os.makedirs(d, exist_ok=True)
        always = ", ".join("a%d" % i for i in range(always_n))
        cond = ", ".join("c%d" % i for i in range(conditional_n))
        body = (
            "# seo-audit\n\n## Steps\n\nDispatch.\n\n"
            "```dispatch\n"
            "orchestrator: seo-audit\n"
            "always:      %s\n"
            "conditional: %s\n"
            "```\n" % (always, cond)
        )
        with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(body)

    def test_eight_plus_seven_split_trips_dispatch_shape(self):
        root = self._tree()
        self._orchestrator_with_split(root, 8, 7)
        ok, detail = _find(vr.check_agent_wellformed(root), "dispatch-shape")
        self.assertFalse(ok, "an 8-always + 7-conditional split must FAIL C3 dispatch-shape; detail=%s" % detail)
        self.assertIn("8-always", detail)

    def test_a_different_split_passes_dispatch_shape(self):
        root = self._tree()
        self._orchestrator_with_split(root, 5, 6)  # the plugin's own derived shape
        ok, detail = _find(vr.check_agent_wellformed(root), "dispatch-shape")
        self.assertTrue(ok, "a 5+6 derived split must PASS dispatch-shape; detail=%s" % detail)


if __name__ == "__main__":
    unittest.main()
