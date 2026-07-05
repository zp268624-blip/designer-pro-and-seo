"""Tests for the modern semantic palette slots (MASTER-PLAN 6.3, W3b DESIGN flagship).

`gen_palettes.py` computes five additive semantic slots per palette -- card / muted /
border / ring / destructive -- deterministically from the palette's existing colors +
the public sRGB relative-luminance formula, and `design_system.py` surfaces them
additively without dropping any existing palette key.

Covers:
  * PRESENCE   -- every generated palette (and the shipped CSV, and design_system's
    output) carries all five new slots as valid #rrggbb hex, alongside the old keys.
  * DETERMINISM -- build_palette is a pure function (same inputs -> byte-identical
    slots twice) and `gen_palettes.py --print` is byte-for-byte reproducible.
  * CONTRAST-SANE -- card/muted stay AA-readable under the palette text; ring and
    destructive clear the WCAG 1.4.11 non-text 3:1 floor against the background; and
    border sits between card and text in luminance (a visible-but-subtle divider).
  * REVERT PATH -- DPS_RANKER=legacy still composes a system with the new slots
    (the slots are data, independent of which ranker picks the row).

Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/`, no pip install.
"""
import argparse
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "design"))
import gen_palettes as gp  # noqa: E402
import design_system as ds  # noqa: E402

DATA = os.path.join(ROOT, "data")
NEW_SLOTS = ("card", "muted", "border", "ring", "destructive")
HEX = __import__("re").compile(r"^#[0-9a-f]{6}$")


def _lum(hexc):
    return gp.relative_luminance(hexc)


class PaletteSlotsPresent(unittest.TestCase):
    def test_build_palette_carries_all_five_slots(self):
        for fam in gp.FAMILIES:
            row = gp.build_palette(*fam)
            for slot in NEW_SLOTS:
                self.assertIn(slot, row, "%s missing %s" % (row["name"], slot))
                self.assertRegex(row[slot], HEX, "%s.%s not #rrggbb" % (row["name"], slot))

    def test_existing_keys_are_not_dropped(self):
        row = gp.build_palette(*gp.FAMILIES[0])
        for key in ("name", "primary", "secondary", "accent", "bg", "surface",
                    "text", "success", "warning", "error", "on_primary",
                    "aa_body_text", "tags", "source", "license"):
            self.assertIn(key, row, "additive change dropped existing key %s" % key)

    def test_shipped_csv_has_the_slots(self):
        rows = ds._load(DATA, "color-palettes.csv")
        self.assertTrue(rows, "color-palettes.csv did not load")
        for r in rows:
            for slot in NEW_SLOTS:
                self.assertIn(slot, r, "CSV row %s missing %s" % (r.get("name"), slot))
                self.assertRegex(r[slot] or "", HEX)


class PaletteSlotsDeterministic(unittest.TestCase):
    def test_build_palette_is_pure(self):
        for fam in gp.FAMILIES:
            self.assertEqual(gp.build_palette(*fam), gp.build_palette(*fam))

    def test_print_is_byte_reproducible(self):
        script = os.path.join(ROOT, "scripts", "design", "gen_palettes.py")
        a = subprocess.run([sys.executable, script, "--print"],
                           capture_output=True, encoding="utf-8")
        b = subprocess.run([sys.executable, script, "--print"],
                           capture_output=True, encoding="utf-8")
        self.assertEqual(a.returncode, 0)
        self.assertEqual(a.stdout, b.stdout, "gen_palettes --print is not reproducible")
        for slot in NEW_SLOTS:
            self.assertIn(slot, a.stdout.splitlines()[0], "%s not in CSV header" % slot)


class PaletteSlotsContrastSane(unittest.TestCase):
    def test_slots_are_contrast_sane_for_every_palette(self):
        for fam in gp.FAMILIES:
            row = gp.build_palette(*fam)
            name, text, bg = row["name"], row["text"], row["bg"]
            # card + muted stay AA-readable under the palette's body text
            self.assertGreaterEqual(gp.contrast_ratio(text, row["card"]), 4.5,
                                    "%s: text on card < AA" % name)
            self.assertGreaterEqual(gp.contrast_ratio(text, row["muted"]), 4.5,
                                    "%s: text on muted < AA" % name)
            # ring + destructive clear the WCAG 1.4.11 non-text 3:1 floor vs the bg
            self.assertGreaterEqual(gp.contrast_ratio(row["ring"], bg), 3.0,
                                    "%s: ring vs bg < 3:1" % name)
            self.assertGreaterEqual(gp.contrast_ratio(row["destructive"], bg), 3.0,
                                    "%s: destructive vs bg < 3:1" % name)
            # border is a visible-but-subtle divider: darker than card, lighter than text
            self.assertLess(_lum(row["border"]), _lum(row["card"]),
                            "%s: border not darker than card" % name)
            self.assertGreater(_lum(row["border"]), _lum(text),
                               "%s: border not lighter than text" % name)


class PaletteSlotsSurfaced(unittest.TestCase):
    def _compose(self, ranker):
        args = argparse.Namespace(product_type="saas-landing", industry="saas",
                                  keywords="modern, trustworthy, minimal",
                                  data_dir=None, human=False, ranker=ranker)
        return ds.compose(args)

    def test_design_system_surfaces_slots_matching_the_row(self):
        rows = {r["name"]: r for r in ds._load(DATA, "color-palettes.csv")}
        out = self._compose("new")
        pal = out["palette"]
        self.assertIsNotNone(pal)
        src = rows[pal["name"]]
        for slot in NEW_SLOTS:
            self.assertIn(slot, pal, "design_system palette missing %s" % slot)
            self.assertEqual(pal[slot], src[slot], "%s surfaced != CSV value" % slot)

    def test_legacy_revert_path_still_surfaces_slots(self):
        pal = self._compose("legacy")["palette"]
        for slot in NEW_SLOTS:
            self.assertIn(slot, pal)
            self.assertRegex(pal[slot] or "", HEX)


if __name__ == "__main__":
    unittest.main()
