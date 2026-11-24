"""Version 59 (explicit go, 24.11.2026 23:58): one idle pose interval, fixed English built-in pose commands, one
failover for every pose command, no German phrases (test_v59_items.py). Version everywhere and English release notes."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__
from aibody_companion import setup as first_start

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


class VersionTests(TestCase):
    def test_version_59_everywhere(self):
        self.assertEqual(__version__, "59")
        self.assertIn('PluginVersion = "59"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "59"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 59)
        self.assertTrue(re.search(r"d0n\.AIBody\.59:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 59 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.58", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 59, package `d0n.AIBody.59.var`, release `v59`", readme)
        self.assertIn("Idle pose interval (s)", readme)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 59, release; explicit go 24.11.2026 23:58)", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T107", "## T108", "## T109", "## T110"):
            self.assertIn(step, proto)
        self.assertIn("idle_pose_interval_s", (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8"))

    def test_release_notes_english_without_personal_names(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v59**", notes)
        for part in ("d0n.AIBody.59.var", "Idle pose interval (s)", "25 %", "lie down", "kneel down", "Handstand",
                     "Stand On Your Left Leg", "idle pool", "Idle default pose", "T107", "T110"):
            self.assertIn(part, notes)
        self.assertIsNone(re.search(r"\b(" + "Le" + "on|Don)\b", notes),
                          "no personal names in public release notes")
