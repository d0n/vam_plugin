"""Version 41 (Leon, 21.11.2026 17:01-17:27): installer VaM folder, Reset to Default, AIBody on BryanGosling, speech audio
fix, all xAI voices, every persona, Apply pose command, right column, no spoken tool calls."""
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
    def test_version_41_everywhere(self):
        self.assertEqual(__version__, "41")
        self.assertIn('PluginVersion = "41"', source("AIBody.cs"))
        self.assertIn('version = "41"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 41)
        self.assertTrue(re.search(r"d0n\.AIBody\.41:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 41 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 41, package `d0n.AIBody.41.var`, release `v41`", readme)
        start = readme[readme.index("## Getting started"):readme.index("### For developers")]
        for part in ("AIBody Companion Setup.exe", "More info", "Run anyway", "Start menu", "Start with Windows",
                     "127.0.0.1", "Add Plugin"):
            self.assertIn(part, start)
        self.assertNotIn("python -m", start)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 41, release; Leon, calls 17:01-17:27, GO for v41 at 17:19): package `d0n.AIBody.41.var`, tag `v41`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T52", "## T53", "## T54", "## T55", "## T56", "## T57", "## T58"):
            self.assertIn(step, tp)

    def test_release_notes(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v41**", notes)
        self.assertNotIn("<next>", notes)
        for part in ("Speech audio never played", "Apply pose command", "28 built-in xAI voices", "(none), Anna, Marc",
                     "wait for **OK**", "T52 to T58"):
            self.assertIn(part, notes)

    def test_scene_plugin_on_bryan(self):
        scene = json.loads((ROOT / "examples" / "scenes" / "AI-Buddy.json").read_text(encoding="utf-8"))
        holders = []
        for atom in scene["atoms"]:
            for st in atom.get("storables", []):
                if st.get("id") == "PluginManager" and st.get("plugins"):
                    holders.append((atom["id"], dict(st["plugins"])))
        self.assertEqual(holders, [("BryanGosling", {"plugin#0": "d0n.AIBody.41:/Custom/Scripts/d0n/AIBody/AIBody.cslist"})])
