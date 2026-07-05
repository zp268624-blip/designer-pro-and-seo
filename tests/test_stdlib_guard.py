"""C11 tests for scripts/verify_release.py: scripts/** must import only the stdlib (now
based on sys.stdlib_module_names) plus local sibling modules, and dynamic imports must be
caught -- a string-literal module is checked like any import; a non-literal one is reported
as unverifiable.

Runs under BOTH `py -m unittest discover -s tests` and `pytest tests/`, no pip install.
Fixtures live only in a throwaway temp root.
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_release as vr  # noqa: E402


class StdlibGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dps_c11_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _script(self, name, body):
        d = os.path.join(self.tmp, "scripts")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            f.write(body)

    def _row(self):
        rows = vr.check_stdlib_only(self.tmp)
        self.assertEqual(len(rows), 1)
        return rows[0]  # (name, ok, detail)

    def test_stdlib_only_passes(self):
        # Includes roots that are NOT in the hand-maintained fallback list (email, uuid,
        # queue, threading) to prove sys.stdlib_module_names is the source of truth (FIX 8).
        self._script("ok.py",
                     "import os, sys, json, re\n"
                     "import email, uuid, queue, threading\n"
                     "from urllib.request import urlopen\n")
        _, ok, detail = self._row()
        self.assertTrue(ok, detail)

    def test_static_thirdparty_import_fails(self):
        self._script("bad.py", "import requests\n")
        _, ok, detail = self._row()
        self.assertFalse(ok, detail)
        self.assertIn("requests", detail)

    def test_dunder_import_literal_thirdparty_fails(self):
        # FIX 3: __import__("requests") must FAIL C11.
        self._script("dyn.py", '__import__("requests")\n')
        _, ok, detail = self._row()
        self.assertFalse(ok, detail)
        self.assertIn("requests", detail)

    def test_importlib_import_module_literal_thirdparty_fails(self):
        self._script("dyn2.py", 'import importlib\nimportlib.import_module("pandas")\n')
        _, ok, detail = self._row()
        self.assertFalse(ok, detail)
        self.assertIn("pandas", detail)

    def test_dynamic_nonliteral_import_is_unverifiable(self):
        # A computed module name cannot be proven stdlib-only -> reported, must FAIL.
        self._script("dyn3.py", "name = 'requests'\n__import__(name)\n")
        _, ok, detail = self._row()
        self.assertFalse(ok, detail)
        self.assertIn("dynamic import", detail)

    def test_dunder_import_literal_stdlib_passes(self):
        self._script("dynok.py", '__import__("json")\n')
        _, ok, detail = self._row()
        self.assertTrue(ok, detail)

    # --- FIX A: aliased / from-imported dynamic-import bindings must not bypass C11 -----
    def test_importlib_alias_attr_thirdparty_fails(self):
        # `import importlib as il` then `il.import_module("requests")` -- the old literal-only
        # check (fn.value.id == "importlib") missed the alias; it must FAIL now.
        self._script("alias_attr.py",
                     'import importlib as il\nil.import_module("requests")\n')
        _, ok, detail = self._row()
        self.assertFalse(ok, detail)
        self.assertIn("requests", detail)

    def test_from_import_module_thirdparty_fails(self):
        # `from importlib import import_module` then `import_module("requests")` must FAIL.
        self._script("from_import.py",
                     'from importlib import import_module\nimport_module("requests")\n')
        _, ok, detail = self._row()
        self.assertFalse(ok, detail)
        self.assertIn("requests", detail)

    def test_from_import_module_aliased_thirdparty_fails(self):
        # `from importlib import import_module as Y` then `Y("requests")` must FAIL.
        self._script("from_import_as.py",
                     'from importlib import import_module as Y\nY("requests")\n')
        _, ok, detail = self._row()
        self.assertFalse(ok, detail)
        self.assertIn("requests", detail)

    def test_importlib_star_import_thirdparty_fails(self):
        # `from importlib import *` then `import_module("requests")` -- the wildcard binds
        # import_module unqualified; it must be tracked and FAIL (Codex round-3 blocker).
        self._script("star_import.py",
                     'from importlib import *\nimport_module("requests")\n')
        _, ok, detail = self._row()
        self.assertFalse(ok, detail)
        self.assertIn("requests", detail)

    def test_getattr_importlib_thirdparty_fails(self):
        # getattr(importlib, "import_module")("requests") -- getattr dynamic dispatch must FAIL.
        self._script("getattr_dyn.py",
                     'import importlib\ngetattr(importlib, "import_module")("requests")\n')
        _, ok, detail = self._row()
        self.assertFalse(ok, detail)
        self.assertIn("requests", detail)

    def test_assignment_alias_from_import_thirdparty_fails(self):
        # `from importlib import import_module; loader = import_module; loader("requests")` FAILS.
        self._script("assign_alias.py",
                     'from importlib import import_module\nloader = import_module\nloader("requests")\n')
        _, ok, detail = self._row()
        self.assertFalse(ok, detail)
        self.assertIn("requests", detail)

    def test_assignment_alias_attr_thirdparty_fails(self):
        # `import importlib; load = importlib.import_module; load("requests")` FAILS.
        self._script("assign_alias_attr.py",
                     'import importlib\nload = importlib.import_module\nload("requests")\n')
        _, ok, detail = self._row()
        self.assertFalse(ok, detail)
        self.assertIn("requests", detail)

    def test_importlib_alias_attr_stdlib_literal_passes(self):
        # `import importlib as il; il.import_module("json")` -- a stdlib literal still PASSES.
        self._script("alias_attr_ok.py",
                     'import importlib as il\nil.import_module("json")\n')
        _, ok, detail = self._row()
        self.assertTrue(ok, detail)


if __name__ == "__main__":
    unittest.main()
