"""Version 42 (Leon, 21.11.2026 18:27 and 18:33): pose menu (choosing applies, Add Pose with the file browser, Delete
Pose, Reset poses), AIBody on 'Client' driving 'AI' in his scene, version check, realtime answer after a tool call,
scrollable Voice menu. The item tests are in test_version42_items.py."""
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
    def test_version_42_everywhere(self):
        self.assertEqual(__version__, "42")
        self.assertIn('PluginVersion = "42"', source("AIBody.cs"))
        self.assertIn('version = "42"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 42)
        self.assertTrue(re.search(r"d0n\.AIBody\.42:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 42 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 42, package `d0n.AIBody.42.var`, release `v42`", readme)
        start = readme[readme.index("## Getting started"):readme.index("### For developers")]
        for part in ("AIBody Companion Setup.exe", "More info", "Run anyway", "Start menu", "Start with Windows",
                     "127.0.0.1", "Add Plugin"):
            self.assertIn(part, start)
        self.assertNotIn("python -m", start)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 42, release; Leon, 18:27 and 18:33, GO for v42 at 18:33 once everything is done): package `d0n.AIBody.42.var`, tag `v42`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T59", "## T60", "## T61", "## T62", "## T63", "## T64"):
            self.assertIn(step, tp)

    def test_release_notes(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v42**", notes)
        self.assertNotIn("<next>", notes)
        for part in ("plugin=40", "Reset poses", "Add Pose", "Delete Pose", "'Client'", "28", "T59 to T64", "not verified"):
            self.assertIn(part, notes)
