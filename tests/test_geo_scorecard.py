"""Wave-3a seo-geo depth: the weighted GEO scorecard, the AI-crawler-policy verdict,
and passage-level citability scoring on geo_check.py.

Every case is OFFLINE (no network, no key): content is a temp file, the robots policy
is a fixture / temp file, and the scorecard is computed from those signals alone. The
new behavior is purely ADDITIVE -- the existing `--content --no-network` citability
output must stay byte-identical in shape (the smoke test depends on it).

Runs under both `py -m unittest discover -s tests` and `pytest tests/`; no pip install.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = os.path.join(ROOT, "scripts", "seo", "geo_check.py")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

sys.path.insert(0, os.path.join(ROOT, "scripts", "seo"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "workflow"))
import geo_check  # noqa: E402


def run(args):
    """Run the CLI; return (returncode, parsed_json_or_None, stdout)."""
    r = subprocess.run([sys.executable, GEO] + args,
                       capture_output=True, encoding="utf-8")
    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        data = None
    return r.returncode, data, r.stdout


def _content_file(td, text):
    p = os.path.join(td, "c.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


# A strongly citable answer-first passage: specific (numbers + year + named source),
# self-contained (no back-reference), and it leads with the answer.
STRONG = ("Cedar benches last 20 to 25 years outdoors before the slats need "
          "replacing, according to a 2025 durability test by the Outdoor "
          "Furniture Council.")
# A vague passage: no specific signal, opens with a back-reference, no answer. Long
# enough to clear the passage floor so the scorer actually keeps it.
VAGUE = ("It is generally considered a good choice for most outdoor settings, "
         "and many buyers seem happy with it overall.")


class PassageCitabilityTest(unittest.TestCase):
    def test_sourced_selfcontained_answerfirst_scores_high(self):
        with tempfile.TemporaryDirectory() as td:
            cf = _content_file(td, "<p>%s</p>" % STRONG)
            rc, data, _ = run(["--content", cf, "--no-network"])
            self.assertEqual(rc, 0)
            cit = data["citability"]
            self.assertEqual(cit["citable"], 1)
            passage = cit["weak"][0] if cit["weak"] else None
            # the strong passage is NOT weak; find it in the full per-passage scoring
            # via the mean -- a single strong passage means a high mean.
            self.assertGreaterEqual(cit["citability_mean"], 85)

    def test_passage_fields_present_and_strong_passage_flags(self):
        # direct unit check of the per-passage scorer
        res = geo_check.passage_citability(STRONG)
        self.assertTrue(res["sourced"])
        self.assertTrue(res["self_contained"])
        self.assertTrue(res["answer_first"])
        self.assertTrue(res["citable"])
        self.assertGreaterEqual(res["citability_score"], 85)

    def test_vague_passage_scores_low(self):
        res = geo_check.passage_citability(VAGUE)
        self.assertFalse(res["sourced"])
        self.assertFalse(res["self_contained"])
        self.assertFalse(res["citable"])
        self.assertLess(res["citability_score"], 40)

    def test_leading_question_is_not_answer_first(self):
        res = geo_check.passage_citability(
            "How long does a cedar bench last? About 20 years on average.")
        self.assertFalse(res["answer_first"])

    def test_existing_content_no_network_still_green(self):
        # the smoke-test contract: --content --no-network emits a citability block with
        # the original keys, JSON parses, exit 0.
        with tempfile.TemporaryDirectory() as td:
            cf = _content_file(td, "<p>%s</p><p>%s</p>" % (STRONG, VAGUE))
            rc, data, _ = run(["--content", cf, "--no-network"])
            self.assertEqual(rc, 0)
            cit = data["citability"]
            for k in ("passages", "citable", "citable_pct", "weak"):
                self.assertIn(k, cit)
            self.assertEqual(cit["passages"], 2)
            self.assertEqual(cit["citable"], 1)

    def test_passage_scoring_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            cf = _content_file(td, "<p>%s</p><p>%s</p>" % (STRONG, VAGUE))
            _, _, out1 = run(["--content", cf, "--no-network"])
            _, _, out2 = run(["--content", cf, "--no-network"])
            self.assertEqual(out1, out2)


class CrawlerPolicyTest(unittest.TestCase):
    def test_analyze_robots_citable_training_blocked(self):
        text = open(os.path.join(FIXTURES, "geo_robots_citable.txt"),
                    encoding="utf-8").read()
        v = geo_check.analyze_robots(text)
        self.assertEqual(v["retrieval_stance"], "open")
        self.assertEqual(v["training_stance"], "blocked")
        self.assertEqual(v["verdict"], "citable-training-blocked")
        self.assertIn("GPTBot", v["training_bots"]["blocked"])
        self.assertIn("OAI-SearchBot", v["retrieval_bots"]["allowed"])

    def test_robots_flag_offline_sets_verdict(self):
        rc, data, _ = run(["--robots", os.path.join(FIXTURES, "geo_robots_citable.txt"),
                           "--no-network"])
        self.assertEqual(rc, 0)
        self.assertEqual(data["ai_crawler_policy"]["verdict"], "citable-training-blocked")

    def test_retrieval_blocked_robots(self):
        # blocking a retrieval bot is the anti-pattern -- it should be flagged.
        text = ("User-agent: OAI-SearchBot\nDisallow: /\n\n"
                "User-agent: PerplexityBot\nDisallow: /\n\n"
                "User-agent: Claude-SearchBot\nDisallow: /\n\n"
                "User-agent: *\nDisallow:\n")
        v = geo_check.analyze_robots(text)
        self.assertEqual(v["retrieval_stance"], "blocked")
        self.assertEqual(v["verdict"], "retrieval-blocked")


class ScorecardTest(unittest.TestCase):
    def test_scorecard_score_and_grade(self):
        with tempfile.TemporaryDirectory() as td:
            cf = _content_file(td, "<p>%s</p>" % STRONG)
            rc, data, _ = run(["--content", cf,
                               "--robots", os.path.join(FIXTURES, "geo_robots_citable.txt"),
                               "--scorecard", "--no-network"])
            self.assertEqual(rc, 0)
            gs = data["geo_score"]
            self.assertIsInstance(gs["score"], int)
            self.assertTrue(0 <= gs["score"] <= 100)
            self.assertIn(gs["grade"], ("strong", "solid", "developing", "weak"))
            names = {c["name"] for c in gs["categories"]}
            self.assertEqual(names, {"passage_citability", "structured_data",
                                     "ai_crawler_access", "llms_txt"})
            # crawler is available here (robots supplied), llms_txt is not (offline)
            avail = {c["name"]: c["available"] for c in gs["categories"]}
            self.assertTrue(avail["ai_crawler_access"])
            self.assertFalse(avail["llms_txt"])

    def test_scorecard_offline_content_only_excludes_crawler_and_llms(self):
        with tempfile.TemporaryDirectory() as td:
            cf = _content_file(td, "<p>%s</p>" % STRONG)
            rc, data, _ = run(["--content", cf, "--scorecard", "--no-network"])
            self.assertEqual(rc, 0)
            gs = data["geo_score"]
            avail = {c["name"]: c["available"] for c in gs["categories"]}
            self.assertTrue(avail["passage_citability"])
            self.assertTrue(avail["structured_data"])
            self.assertFalse(avail["ai_crawler_access"])
            self.assertFalse(avail["llms_txt"])
            self.assertEqual(gs["available_weight"], 45 + 20)

    def test_retrieval_block_tanks_crawler_category(self):
        with tempfile.TemporaryDirectory() as td:
            cf = _content_file(td, "<p>%s</p>" % STRONG)
            rp = os.path.join(td, "robots.txt")
            with open(rp, "w", encoding="utf-8") as f:
                f.write("User-agent: OAI-SearchBot\nDisallow: /\n\n"
                        "User-agent: PerplexityBot\nDisallow: /\n\n"
                        "User-agent: Claude-SearchBot\nDisallow: /\n\n"
                        "User-agent: *\nDisallow:\n")
            rc, data, _ = run(["--content", cf, "--robots", rp,
                               "--scorecard", "--no-network"])
            self.assertEqual(rc, 0)
            cat = {c["name"]: c for c in data["geo_score"]["categories"]}
            self.assertEqual(cat["ai_crawler_access"]["score"], 0)

    def test_scorecard_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            cf = _content_file(td, "<p>%s</p>" % STRONG)
            a = run(["--content", cf, "--scorecard", "--no-network"])[2]
            b = run(["--content", cf, "--scorecard", "--no-network"])[2]
            self.assertEqual(a, b)


class HumanAsciiTest(unittest.TestCase):
    """FIX 6: the --human render path must be pure ASCII (the contract promises ASCII
    human output) on both the passage-citability and the scorecard paths."""
    @staticmethod
    def _is_ascii(s):
        try:
            s.encode("ascii")
            return True
        except UnicodeEncodeError:
            return False

    def test_human_passage_path_is_ascii(self):
        with tempfile.TemporaryDirectory() as td:
            cf = _content_file(td, "<p>%s</p><p>%s</p>" % (STRONG, VAGUE))
            rc, _, out = run(["--content", cf, "--no-network", "--human"])
            self.assertEqual(rc, 0)
            self.assertTrue(self._is_ascii(out), "human passage output must be pure ASCII")

    def test_human_scorecard_path_is_ascii(self):
        with tempfile.TemporaryDirectory() as td:
            cf = _content_file(td, "<p>%s</p>" % STRONG)
            rc, _, out = run(["--content", cf,
                              "--robots", os.path.join(FIXTURES, "geo_robots_citable.txt"),
                              "--scorecard", "--no-network", "--human"])
            self.assertEqual(rc, 0)
            self.assertTrue(self._is_ascii(out), "scorecard human output must be pure ASCII")


class BadInputTest(unittest.TestCase):
    def test_missing_robots_file_errors_nonzero(self):
        rc, data, _ = run(["--robots", os.path.join(FIXTURES, "does-not-exist.txt"),
                           "--no-network"])
        self.assertNotEqual(rc, 0)
        self.assertTrue(data is not None and data.get("errors"))


if __name__ == "__main__":
    unittest.main()
