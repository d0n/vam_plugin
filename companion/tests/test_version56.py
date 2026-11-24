"""Version 56 (Leon, voice 24.11.2026 15:27-15:30, explicit go): pose changes keep her place, companion pose commands,
Idle Poser, Reset with Dollmaster, realtime without VaM (test_v56_pose_guard.py). Version everywhere, English notes."""
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
    def test_version_56_everywhere(self):
        self.assertEqual(__version__, "56")
        self.assertIn('PluginVersion = "56"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "56"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 56)
        self.assertTrue(re.search(r"d0n\.AIBody\.56:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 56 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.55", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 56, package `d0n.AIBody.56.var`, release `v56`", readme)
        self.assertIn("PoseGuard", readme)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 56, release; Leon, voice 24.11.2026 15:27-15:30", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T97", "## T98", "## T99", "## T100", "## T101"):
            self.assertIn(step, proto)

    def test_release_notes_english(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v56**", notes)
        for part in ("d0n.AIBody.56.var", "position AND facing direction", "Pose command (voice) applied",
                     "pause 30 s", "Reset to Default", "Auto Expressions", "realtime session", "T97", "T101"):
            self.assertIn(part, notes)
