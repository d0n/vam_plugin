"""Version 52 (Leon, call 22.11.2026 20:47-20:48, explicit go): pose commands / Apply Pose / twitching / pose menu race
(test_v52_poses.py). Version everywhere and English release notes."""
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
    def test_version_52_everywhere(self):
        self.assertEqual(__version__, "52")
        self.assertIn('PluginVersion = "52"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "52"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 52)
        self.assertTrue(re.search(r"d0n\.AIBody\.52:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 52 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.51", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 52, package `d0n.AIBody.52.var`, release `v52`", readme)
        self.assertIn("(version 52, release; Leon, call 20:47-20:48", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        self.assertIn("## T87", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))

    def test_release_notes_english(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v52**", notes)
        for part in ("d0n.AIBody.52.var", "loaded once", "Load On Select", "twitching", "Dollmaster", "Body control",
                     "Apply Pose", "only selects it", "Idle default pose", "Apply idle default pose", ".vap", "T87"):
            self.assertIn(part, notes)
