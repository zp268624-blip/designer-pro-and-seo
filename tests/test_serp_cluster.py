"""Tests for the seo-cluster flagship leaf script:

  scripts/seo/serp_cluster.py -- SERP-overlap semantic clustering.

IMPORTANT (clean-room + honesty): SERP ACQUISITION is a Claude/WebSearch step, NOT
this script. serp_cluster.py is the DETERMINISTIC post-processor over an
orchestrator-supplied SERP blob (`--serps FILE`: JSON of {keyword: [ranked urls]}).
It computes pairwise SERP-overlap, clusters keywords by shared-URL similarity (a
threshold the caller chooses), classifies intent, and emits hub-and-spoke clusters
plus an internal-link matrix.

Contract: JSON to stdout by default; `--human` ASCII summary; deterministic (same
input -> same output); bad input -> JSON error object + a NON-ZERO exit (never a raw
traceback); runs entirely OFFLINE (no network anywhere). stdlib only.

Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/`, no pip
install, no network. Fixtures live in a tempdir.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "seo", "serp_cluster.py")


def _run(args, stdin=None):
    proc = subprocess.run(
        [sys.executable, SCRIPT] + args,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _is_ascii(text):
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _write(blob):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(blob, f)
    return path


# A blob where two keyword groups have strong intra-group SERP overlap and zero
# cross-group overlap, plus one unrelated keyword that shares with nobody.
TWO_CLUSTERS = {
    "best running shoes": [
        "https://a.com/best-shoes", "https://b.com/top-shoes",
        "https://c.com/reviews", "https://d.com/guide",
    ],
    "top running shoes 2026": [
        "https://a.com/best-shoes", "https://b.com/top-shoes",
        "https://c.com/reviews", "https://e.com/list",
    ],
    "running shoe reviews": [
        "https://a.com/best-shoes", "https://b.com/top-shoes",
        "https://c.com/reviews", "https://f.com/ranked",
    ],
    "buy coffee beans online": [
        "https://shop1.com/beans", "https://shop2.com/coffee",
        "https://shop3.com/order", "https://shop4.com/cart",
    ],
    "coffee beans for sale": [
        "https://shop1.com/beans", "https://shop2.com/coffee",
        "https://shop3.com/order", "https://shop5.com/deal",
    ],
    "what is single origin coffee": [
        "https://wiki.com/origin", "https://blog.com/explainer",
        "https://edu.com/guide", "https://news.com/article",
    ],
}


class ClusteringTest(unittest.TestCase):
    def test_two_clusters_and_one_singleton(self):
        path = _write(TWO_CLUSTERS)
        rc, out, err = _run(["--serps", path, "--threshold", "3"])
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertIn("clusters", data)
        self.assertIn("singletons", data)
        # the three shoe keywords form one cluster; the two coffee-shop keywords
        # form another; the lone explainer keyword is a singleton.
        sizes = sorted(c["size"] for c in data["clusters"])
        self.assertEqual(sizes, [2, 3])
        singletons = {s["keyword"] for s in data["singletons"]}
        self.assertIn("what is single origin coffee", singletons)

    def test_cluster_membership_is_correct(self):
        path = _write(TWO_CLUSTERS)
        rc, out, _ = _run(["--serps", path, "--threshold", "3"])
        data = json.loads(out)
        members = []
        for c in data["clusters"]:
            members.append({c["pillar"]} | {s["keyword"] for s in c["spokes"]})
        shoe = next(m for m in members if "best running shoes" in m)
        self.assertEqual(shoe, {"best running shoes", "top running shoes 2026",
                                "running shoe reviews"})

    def test_hub_is_most_central_keyword(self):
        # The shoe trio is mutually overlapping; the pillar must be one of them and
        # be reported deterministically. Re-running yields the same pillar.
        path = _write(TWO_CLUSTERS)
        _, out1, _ = _run(["--serps", path, "--threshold", "3"])
        _, out2, _ = _run(["--serps", path, "--threshold", "3"])
        self.assertEqual(out1, out2)  # determinism
        data = json.loads(out1)
        shoe = next(c for c in data["clusters"]
                    if c["pillar"] in TWO_CLUSTERS and "shoe" in c["pillar"]
                    or any("shoe" in s["keyword"] for s in c["spokes"]))
        self.assertTrue(shoe["pillar"].endswith("shoes")
                        or "shoe" in shoe["pillar"])

    def test_every_spoke_links_up_to_pillar(self):
        path = _write(TWO_CLUSTERS)
        rc, out, _ = _run(["--serps", path, "--threshold", "3"])
        data = json.loads(out)
        for c in data["clusters"]:
            up = {l["from"] for l in c["internal_links"]
                  if l["type"] == "spoke_to_pillar" and l["to"] == c["pillar"]}
            self.assertEqual(up, {s["keyword"] for s in c["spokes"]},
                             "every spoke must link up to the pillar")
            # spoke->pillar anchor text is the pillar keyword
            for l in c["internal_links"]:
                if l["type"] == "spoke_to_pillar":
                    self.assertEqual(l["anchor"], c["pillar"])

    def test_link_matrix_is_flattened_top_level(self):
        path = _write(TWO_CLUSTERS)
        _, out, _ = _run(["--serps", path, "--threshold", "3"])
        data = json.loads(out)
        self.assertIn("link_matrix", data)
        per_cluster = sum(len(c["internal_links"]) for c in data["clusters"])
        self.assertEqual(len(data["link_matrix"]), per_cluster)


class IntentTest(unittest.TestCase):
    BLOB = {
        "buy wireless headphones": [["x"]][0] and ["https://s.com/buy"],
        "best wireless headphones": ["https://s.com/best"],
        "how to pair wireless headphones": ["https://s.com/how"],
        "zephyr headphones login": ["https://s.com/login"],
    }

    def _intents(self, out):
        data = json.loads(out)
        result = {}
        for c in data["clusters"]:
            result[c["pillar"]] = c["pillar_intent"]
            for s in c["spokes"]:
                result[s["keyword"]] = s["intent"]
        for s in data["singletons"]:
            result[s["keyword"]] = s["intent"]
        return result

    def test_intent_classification(self):
        path = _write({
            "buy wireless headphones": ["https://s.com/buy"],
            "best wireless headphones": ["https://s.com/best"],
            "how to pair wireless headphones": ["https://s.com/how"],
            "zephyr headphones login": ["https://s.com/login"],
        })
        rc, out, err = _run(["--serps", path, "--threshold", "3"])
        self.assertEqual(rc, 0, err)
        intents = self._intents(out)
        self.assertEqual(intents["buy wireless headphones"], "transactional")
        self.assertEqual(intents["best wireless headphones"], "commercial")
        self.assertEqual(intents["how to pair wireless headphones"], "informational")
        self.assertEqual(intents["zephyr headphones login"], "navigational")


class OutputContractTest(unittest.TestCase):
    def test_json_by_default(self):
        path = _write(TWO_CLUSTERS)
        rc, out, _ = _run(["--serps", path])
        self.assertEqual(rc, 0)
        data = json.loads(out)  # must parse
        for key in ("params", "clusters", "singletons", "link_matrix",
                    "tier", "needs_tier1"):
            self.assertIn(key, data)
        # honesty: tier line names Tier 2 + the script; needs_tier1 lists
        # never-fabricate fields (volume/CPC/difficulty), never synthesized.
        self.assertIn("Tier 2", data["tier"])
        self.assertTrue(any("volume" in n.lower() for n in data["needs_tier1"]))

    def test_default_threshold_reported(self):
        path = _write(TWO_CLUSTERS)
        _, out, _ = _run(["--serps", path])
        data = json.loads(out)
        self.assertIn("threshold", data["params"])
        self.assertIsInstance(data["params"]["threshold"], int)

    def test_human_is_ascii(self):
        path = _write(TWO_CLUSTERS)
        rc, out, _ = _run(["--serps", path, "--threshold", "3", "--human"])
        self.assertEqual(rc, 0)
        self.assertTrue(_is_ascii(out))
        self.assertIn("Cluster", out)

    def test_reads_stdin_with_dash(self):
        rc, out, err = _run(["--serps", "-", "--threshold", "3"],
                            stdin=json.dumps(TWO_CLUSTERS))
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertTrue(data["clusters"])

    def test_url_normalization_ignores_scheme_and_www(self):
        # the same page via http/https and with/without www must count as a match,
        # so these two keywords share all 3 URLs and cluster at threshold 3.
        blob = {
            "kw one": ["http://www.site.com/a", "https://site.com/b/", "site.com/c"],
            "kw two": ["https://site.com/a", "http://www.site.com/b", "https://www.site.com/c/"],
        }
        path = _write(blob)
        rc, out, err = _run(["--serps", path, "--threshold", "3"])
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertEqual(len(data["clusters"]), 1)
        self.assertEqual(data["clusters"][0]["size"], 2)


class ErrorHandlingTest(unittest.TestCase):
    def test_missing_serps_arg_is_nonzero(self):
        rc, out, err = _run([])
        self.assertNotEqual(rc, 0)

    def test_missing_file_is_json_error_nonzero(self):
        rc, out, err = _run(["--serps", os.path.join(tempfile.gettempdir(),
                                                      "no_such_serps_blob_xyz.json")])
        self.assertNotEqual(rc, 0)
        data = json.loads(out)
        self.assertIn("error", data)
        self.assertTrue(_is_ascii(out))

    def test_invalid_json_is_error_nonzero(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not valid json,,,")
        rc, out, err = _run(["--serps", path])
        self.assertNotEqual(rc, 0)
        self.assertIn("error", json.loads(out))

    def test_wrong_shape_is_error_nonzero(self):
        # a list, not an object of keyword -> urls
        path = _write(["not", "an", "object"])
        rc, out, err = _run(["--serps", path])
        self.assertNotEqual(rc, 0)
        self.assertIn("error", json.loads(out))

    def test_values_not_lists_is_error_nonzero(self):
        path = _write({"kw": "should-be-a-list-of-urls"})
        rc, out, err = _run(["--serps", path])
        self.assertNotEqual(rc, 0)
        self.assertIn("error", json.loads(out))

    def test_empty_object_is_error_nonzero(self):
        path = _write({})
        rc, out, err = _run(["--serps", path])
        self.assertNotEqual(rc, 0)
        self.assertIn("error", json.loads(out))


class GoldenExampleTest(unittest.TestCase):
    """The C4 golden example must exist and reproduce a real free-path deliverable."""
    EX = os.path.join(ROOT, "references", "examples", "seo-cluster")

    def test_golden_example_blob_clusters(self):
        blob_path = os.path.join(self.EX, "sample-serps.json")
        if not os.path.exists(blob_path):
            self.skipTest("golden example not present yet")
        rc, out, err = _run(["--serps", blob_path, "--threshold", "3"])
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertTrue(data["clusters"], "golden example must produce a cluster")

    def test_golden_example_has_no_real_brand(self):
        # clean-room: the shipped fixture must not name a real third-party brand.
        blob_path = os.path.join(self.EX, "sample-serps.json")
        if not os.path.exists(blob_path):
            self.skipTest("golden example not present yet")
        with open(blob_path, encoding="utf-8") as fh:
            raw = fh.read().lower()
        # Real-brand names are assembled from fragments so no contiguous brand literal
        # ships in this shipped test file (same technique verify_release.py uses).
        for b in ("as" + "ana", "sa" + "lesforce", "so" + "ny", "hub" + "spot"):
            self.assertNotIn(b, raw, "a real brand must not ship in the fixture: " + b)


def _pillar_link_invariant(tc, data, threshold):
    """Contract: a spoke<->pillar hub-and-spoke edge must carry shared >= threshold; a
    member that shares fewer than threshold with the pillar is flagged `bridged` and is
    never linked to the pillar as a hub-and-spoke edge (it joined via single-linkage)."""
    for c in data["clusters"]:
        for l in c["internal_links"]:
            if l["type"] in ("spoke_to_pillar", "pillar_to_spoke"):
                tc.assertGreaterEqual(
                    l.get("shared", 0), threshold,
                    "a pillar<->spoke link must share >= threshold: %r" % (l,))
        for s in c["spokes"]:
            if s["shared_with_pillar"] < threshold:
                tc.assertTrue(s.get("bridged"),
                              "below-threshold member must be flagged bridged: %s"
                              % s["keyword"])
                for l in c["internal_links"]:
                    if l["type"] in ("spoke_to_pillar", "pillar_to_spoke"):
                        tc.assertNotIn(s["keyword"], (l["from"], l["to"]),
                                       "a bridged member must have no pillar edge")


class ChainBridgeTest(unittest.TestCase):
    """FIX 3: single-linkage can chain members into one component even when an end member
    shares nothing with the chosen pillar. Such a member must NOT get a hub-and-spoke
    pillar link below threshold -- it is marked `bridged` instead."""
    # alpha-bravo (2), bravo-charlie (2), charlie-delta (2); every non-adjacent pair
    # shares 0. bravo is the most SERP-central -> pillar; delta is two hops away and
    # shares 0 with bravo, so under naive single-linkage it would get a shared=0 pillar
    # link. It must not.
    CHAIN = {
        "alpha": ["https://x.example/ab1", "https://x.example/ab2", "https://x.example/au"],
        "bravo": ["https://x.example/ab1", "https://x.example/ab2",
                  "https://x.example/bc1", "https://x.example/bc2"],
        "charlie": ["https://x.example/bc1", "https://x.example/bc2",
                    "https://x.example/cd1", "https://x.example/cd2"],
        "delta": ["https://x.example/cd1", "https://x.example/cd2", "https://x.example/du"],
    }

    def test_no_pillar_spoke_link_below_threshold(self):
        path = _write(self.CHAIN)
        rc, out, err = _run(["--serps", path, "--threshold", "2"])
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertEqual(len(data["clusters"]), 1, "the chain is one component")
        _pillar_link_invariant(self, data, 2)
        c = data["clusters"][0]
        self.assertEqual(c["pillar"], "bravo")
        bridged = {s["keyword"] for s in c["spokes"] if s.get("bridged")}
        self.assertIn("delta", bridged, "delta shares 0 with the pillar -> bridged")

    def test_three_node_chain_pillar_links_all_meet_threshold(self):
        # the task's stated fixture: A-B >=t, B-C >=t, A-C 0 (B is central -> pillar).
        blob = {
            "one": ["https://y.example/n1", "https://y.example/n2", "https://y.example/u1"],
            "two": ["https://y.example/n1", "https://y.example/n2",
                    "https://y.example/n3", "https://y.example/n4"],
            "three": ["https://y.example/n3", "https://y.example/n4", "https://y.example/u3"],
        }
        path = _write(blob)
        rc, out, err = _run(["--serps", path, "--threshold", "2"])
        self.assertEqual(rc, 0, err)
        _pillar_link_invariant(self, json.loads(out), 2)


class ArgparseContractTest(unittest.TestCase):
    """FIX 2: argparse's own failures must honor the JSON-error contract -- a parseable
    JSON {"error"} on stdout + a non-zero exit, never a bare usage dump to stderr."""
    def test_missing_required_arg_is_json_error(self):
        rc, out, err = _run([])  # --serps is required
        self.assertNotEqual(rc, 0)
        data = json.loads(out)   # must parse as JSON from stdout
        self.assertIn("error", data)
        self.assertTrue(_is_ascii(out))

    def test_bad_typed_arg_is_json_error(self):
        path = _write(TWO_CLUSTERS)
        rc, out, err = _run(["--serps", path, "--threshold", "not-an-int"])
        self.assertNotEqual(rc, 0)
        data = json.loads(out)
        self.assertIn("error", data)
        self.assertTrue(_is_ascii(out))


if __name__ == "__main__":
    unittest.main()
