"""Tests for the C7 clean-room guard in scripts/verify_release.py.

Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/` with no pip
install. Every planted marker is SYNTHETIC (ZZSYNTHAUTHOR / ZZSYNTHBRAND) -- never a
real third-party person's name in any committed file. Fixtures live only in a throwaway
temp root, so they never reach the shipped tree (and tests/ is pruned from the real
scan anyway).

Guard model under review (Codex round 1 fixes):
  * The GENERIC family (license markers, the reserved brand token, source-attribution
    headers of any scheme) is HARDCODED and runs UNCONDITIONALLY -- even with no
    .cleanroom-thirdparty (public CI). It is exempt only in the four governance docs.
  * NAMES (denylist literals + copyright-sign+name) are scanned on RAW text with NO
    whole-file exemption: a third-party name may never appear in ANY shipped file,
    including NOTICE.md / PROVENANCE.md and including inside backticks.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_release as vr  # noqa: E402

# Synthetic guard config. ZZSYNTHBRAND is denylisted AND embedded inside an allowlisted
# owner tool ("route-ZZSYNTHBRAND") so the span-aware masking path is exercised meaningfully.
THIRDPARTY = {
    "name_marker_denylist": ["ZZSYNTHAUTHOR", "ZZSYNTHBRAND"],
    "owner_tool_allowlist": ["route-codex", "route-gemini", "route-ZZSYNTHBRAND"],
    "inspiration_counts": [],
}
COPYRIGHT = chr(0xA9)  # copyright sign U+00A9, built without a non-ASCII source byte


class C7GuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dps_c7_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    # --- helpers --------------------------------------------------------------
    def _thirdparty(self, obj=THIRDPARTY, raw=None):
        path = os.path.join(self.tmp, ".cleanroom-thirdparty")
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else json.dumps(obj))

    def _file(self, rel, content):
        p = os.path.join(self.tmp, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    def _row(self):
        rows = vr.check_cleanroom_thirdparty(self.tmp)
        self.assertEqual(len(rows), 1)
        return rows[0]  # (name, ok, detail)

    def _assert_red(self, content, where="skills/x/SKILL.md"):
        self._thirdparty()
        self._file(where, content)
        _, ok, detail = self._row()
        self.assertFalse(ok, "expected C7 RED but got PASS; detail=%s" % detail)

    def _assert_green(self, content, where="skills/x/SKILL.md"):
        self._thirdparty()
        self._file(where, content)
        _, ok, detail = self._row()
        self.assertTrue(ok, "expected C7 PASS but got FAIL; detail=%s" % detail)

    # --- RED cases (each required marker variant) -----------------------------
    def test_denylisted_name_goes_red(self):
        self._assert_red("Methodology authored by ZZSYNTHAUTHOR, used widely.")

    def test_denylisted_name_in_backticks_goes_red(self):
        # FIX 2: NO code-span bypass for names. A name quoted in backticks in a shipped,
        # non-exempt file is still a leak.
        self._assert_red("Adapted from `ZZSYNTHAUTHOR` original prompts.")

    def test_source_attribution_header_goes_red(self):
        self._assert_red("<!-- Source: http://example.test/x -->\n# Page\n")

    def test_source_header_https_goes_red(self):
        self._assert_red("<!-- Source: https://other.example/asset -->")

    def test_source_header_file_scheme_goes_red(self):
        # FIX 4: any scheme, not just http(s).
        self._assert_red("Source: file://x/secret.csv")

    def test_source_header_s3_scheme_goes_red(self):
        self._assert_red("Source: s3://bucket/key")

    def test_cc_by_license_marker_goes_red(self):
        self._assert_red("These prompts are released under CC BY 4.0 terms.")

    def test_copyright_sign_plus_name_goes_red(self):
        self._assert_red("%s ZZSYNTHAUTHOR 2026, all rights reserved." % COPYRIGHT)

    def test_uppercase_brand_token_goes_red(self):
        self._assert_red("Built on the FLOW method end to end.")

    def test_titlecase_brand_framework_goes_red(self):
        # FIX 5: title-case form caught ONLY in "<brand> framework" context.
        self._assert_red("We adopted the Flow framework wholesale.")

    def test_bare_denylisted_brand_goes_red(self):
        # ZZSYNTHBRAND on its own (not inside an owner tool) must still be caught.
        self._assert_red("Adapted from ZZSYNTHBRAND prompts.")

    def test_standalone_name_caught_even_when_also_inside_allowlisted_token(self):
        # FIX 6: span-aware allowlist. route-ZZSYNTHBRAND is allowlisted, but a SECOND,
        # standalone ZZSYNTHBRAND elsewhere is a real leak and must be caught.
        self._assert_red("The route-ZZSYNTHBRAND bridge wraps ZZSYNTHBRAND's own method.")

    def test_name_in_notice_goes_red(self):
        # FIX 7: NOTICE.md is exempt for MARKERS, never for NAMES.
        self._assert_red("Attribution: ZZSYNTHAUTHOR.", where="NOTICE.md")

    def test_name_in_provenance_goes_red(self):
        self._assert_red("Replaces ZZSYNTHAUTHOR's prompts.", where="references/PROVENANCE.md")

    # --- GREEN cases (must NOT false-positive) --------------------------------
    def test_owner_tool_route_codex_not_flagged(self):
        self._assert_green("Route the diff to route-codex; long files to route-gemini.")

    def test_allowlisted_token_masks_embedded_denylist(self):
        # route-ZZSYNTHBRAND is allowlisted; the denylisted ZZSYNTHBRAND inside it is masked.
        self._assert_green("The route-ZZSYNTHBRAND bridge wraps the existing method.")

    def test_lowercase_flow_words_not_flagged(self):
        self._assert_green("This workflow handles overflow and a clean data-flow.")

    def test_titlecase_flow_non_brand_context_not_flagged(self):
        # FIX 5: title-case "Flow" outside "<brand> framework" context must NOT trip.
        self._assert_green("Track the user flow and the Flow of data through each step.")

    def test_marker_exempt_in_notice_file(self):
        # MARKERS (license/brand/source) ARE exempt in the four governance docs.
        self._assert_green("Formerly under CC BY 4.0; see the FLOW notes.", where="NOTICE.md")

    def test_marker_exempt_in_engine_contracts_file(self):
        self._assert_green("Never ship a CC BY banner or a <!-- Source: x --> header.",
                           where="references/ENGINE-CONTRACTS.md")

    def test_tests_tree_is_pruned(self):
        self._assert_green("ZZSYNTHAUTHOR everywhere here.", where="tests/fixtures/bad.md")

    # --- load-contract parity with _load_denylist + FIX 1 (non-inert) ---------
    def test_missing_thirdparty_name_portion_is_vacuous(self):
        # No .cleanroom-thirdparty; the NAME portion is vacuous, so a planted NAME (with no
        # generic marker) does not fail.
        self._file("skills/x/SKILL.md", "ZZSYNTHAUTHOR is here but no config exists.")
        _, ok, detail = self._row()
        self.assertTrue(ok, detail)

    def test_missing_thirdparty_still_enforces_generic_markers(self):
        # FIX 1 (BLOCKER): a missing config must NOT make the WHOLE check inert. The generic
        # marker/brand/source family still fires with no config (this is the public-CI case).
        self._file("skills/x/SKILL.md", "Released under CC BY 4.0 by an upstream author.")
        _, ok, detail = self._row()
        self.assertFalse(ok, "generic markers must still fire with no config; detail=%s" % detail)

    def test_unreadable_thirdparty_fails_loud(self):
        self._thirdparty(raw="{ this is not valid json ")
        self._file("skills/x/SKILL.md", "clean content")
        _, ok, detail = self._row()
        self.assertFalse(ok, "a present-but-unreadable config must FAIL loud")


if __name__ == "__main__":
    unittest.main()
