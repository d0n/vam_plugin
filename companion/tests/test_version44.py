"""Version 44 (Leon, 21.11.2026 20:39-21:09): the setup installs the package and removes older ones, reports an existing
install, closes a running companion, writes a log; Speech volume up to 3. The item tests are in test_version44_items.py."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__
from aibody_companion import setup as first_start

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class VersionTests(TestCase):
    def test_version_44_everywhere(self):
        self.assertEqual(__version__, "44")
        self.assertIn('PluginVersion = "44"', source("AIBody.cs"))
        self.assertIn('version = "44"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 44)
        self.assertTrue(re.search(r"d0n\.AIBody\.44:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 44 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 44, package `d0n.AIBody.44.var`, release `v44`", readme)
        start = readme[readme.index("## Getting started"):readme.index("### For developers")]
        for part in ("AIBody Companion Setup.exe", "More info", "Run anyway", "Start menu", "Start with Windows",
                     "127.0.0.1", "Add Plugin"):
            self.assertIn(part, start)
        self.assertNotIn("python -m", start)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 44, release; Leon, calls 20:39-21:09, release approved at 21:01): package `d0n.AIBody.44.var`, tag `v44`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T70", "## T71", "## T72", "## T73"):
            self.assertIn(step, tp)

    def test_release_notes(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v44**", notes)
        self.assertNotIn("<next>", notes)
        for part in ("Remove older AIBody packages", "Update from AIBody", "Setup log", "up to 3", "T70 to T73"):
            self.assertIn(part, notes)
