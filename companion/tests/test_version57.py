"""Version 57 (Leon, voice 24.11.2026 15:57, explicit go): a failing idle pose is dropped from the pool at once and the
next one is loaded right away (test_v56_pose_guard.IdlePoserTests, test_version35 harness). Version everywhere, notes."""
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
    def test_version_57_everywhere(self):
        self.assertEqual(__version__, "57")
        self.assertIn('PluginVersion = "57"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "57"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 57)
        self.assertTrue(re.search(r"d0n\.AIBody\.57:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 57 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.56", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 57, package `d0n.AIBody.57.var`, release `v57`", readme)
        self.assertIn("Version 57: an idle pose that fails is dropped", readme)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 57, release; Leon, voice 24.11.2026 15:57", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T102",):
            self.assertIn(step, proto)

    def test_release_notes_english(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v57**", notes)
        for part in ("d0n.AIBody.57.var", "dropped from the idle pool immediately", "loaded right away",
                     "no 30 s pause", "no pose left in the idle pool", "T102"):
            self.assertIn(part, notes)
