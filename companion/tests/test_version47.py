"""Version 47 (Leon, 22.11.2026 12:17-12:25): fixes the v46 regression (speech did not start, only the test tone was
heard, sound worse than v45) by going back to v45's head audio handling, removes the Breath morph / Breath1 boxes and
always packs the scene thumbnail next to the scene. The item tests are in test_v47_regression.py. Not released yet."""
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
    def test_version_47_everywhere(self):
        self.assertEqual(__version__, "47")
        self.assertIn('PluginVersion = "47"', source("AIBody.cs"))
        self.assertIn('version = "47"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 47)
        self.assertTrue(re.search(r"d0n\.AIBody\.47:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 47 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 47, package `d0n.AIBody.47.var`, release `v47`", readme)
        self.assertNotIn("full_volume_distance", readme)
        start = readme[readme.index("## Getting started"):readme.index("### For developers")]
        for part in ("AIBody Companion Setup.exe", "More info", "Run anyway", "Start menu", "Start with Windows",
                     "127.0.0.1", "Add Plugin"):
            self.assertIn(part, start)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 47; Leon, 12:17-12:25", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## T76", tp)

    def test_release_notes(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v47**", notes)
        self.assertNotIn("<next>", notes)
        for part in ("d0n.AIBody.47.var", "test tone", "v45", "Breath1", "thumbnail", "T76"):
            self.assertIn(part, notes)
        self.assertNotIn("Full volume distance (m)** (tab", notes)
