"""test_dag.py -- the dependency graph across skills AND agents is a DAG (W4).

ENGINE-CONTRACTS section 4 (amended): the dependency DAG spans skills and agents,
one direction only (orchestrator -> agent -> script). Agents are leaves -- they carry
no Dependencies edges. This test builds the real skill/agent edge set and proves it is
acyclic, plus a planted-cycle negative test so the detector is known to have teeth.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_release as vr  # noqa: E402


def _skill_names(root):
    return {os.path.basename(os.path.dirname(p)) for p in vr.skill_files(root)}


def _agent_names(root):
    return {os.path.splitext(os.path.basename(p))[0] for p in vr._agent_files(root)}


def _build_edges(root):
    """node -> set(dependency nodes). Nodes are skills + agents; an edge is a
    Dependencies entry that names another skill/agent (script/tool deps are ignored)."""
    skills, agents = _skill_names(root), _agent_names(root)
    nodes = skills | agents
    edges = {n: set() for n in nodes}
    for p in vr.skill_files(root):
        name = os.path.basename(os.path.dirname(p))
        deps = vr._dep_entries(vr._section(vr.read(p), "Dependencies"))
        edges[name] = {d for d in deps if d in nodes}
    # agents are leaves (no Dependencies section / no skill edges) -- already {} above.
    return edges


def _find_cycle(edges):
    """Return a cycle path if the directed graph has one, else None (DFS 3-color)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in edges}

    def dfs(u, stack):
        color[u] = GRAY
        for v in edges.get(u, ()):
            if v not in color:
                continue
            if color[v] == GRAY:
                return stack + [u, v]
            if color[v] == WHITE:
                got = dfs(v, stack + [u])
                if got:
                    return got
        color[u] = BLACK
        return None

    for n in edges:
        if color[n] == WHITE:
            got = dfs(n, [])
            if got:
                return got
    return None


class DagTest(unittest.TestCase):
    def test_skill_agent_graph_is_acyclic(self):
        cyc = _find_cycle(_build_edges(ROOT))
        self.assertIsNone(cyc, "dependency cycle across skills+agents: %s" % (cyc,))

    def test_agents_are_dag_leaves(self):
        # one-directional orchestrator -> agent -> script: an agent carries no
        # Dependencies edge to any *skill or agent* node (a bundled-script dep is fine).
        nodes = _skill_names(ROOT) | _agent_names(ROOT)
        for p in vr._agent_files(ROOT):
            deps = set(vr._dep_entries(vr._section(vr.read(p), "Dependencies")))
            edges = deps & nodes
            self.assertEqual(
                edges, set(),
                "agent %s must be a DAG leaf (no skill/agent Dependencies edges); found %s"
                % (os.path.basename(p), sorted(edges)),
            )

    def test_planted_cycle_is_detected(self):
        # prove the detector trips on a real cycle (RED-before-GREEN discipline).
        self.assertIsNotNone(_find_cycle({"a": {"b"}, "b": {"a"}}), "a<->b must be flagged")
        self.assertIsNotNone(
            _find_cycle({"a": {"b"}, "b": {"c"}, "c": {"a"}}), "a->b->c->a must be flagged")
        self.assertIsNone(_find_cycle({"a": {"b"}, "b": {"c"}, "c": set()}), "a->b->c is acyclic")


if __name__ == "__main__":
    unittest.main()
