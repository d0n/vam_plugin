"""Version 54 (Leon, voice 22.11.2026 23:27-23:31, explicit go): scene without Freeze state, thumbnail pair, Body
position that moves the whole character and stays, idle pool from the AIBody pose folder, speech backlog fixes
(test_v54_items.py). Version everywhere and English release notes."""
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
    def test_version_54_everywhere(self):
        self.assertEqual(__version__, "54")
        self.assertIn('PluginVersion = "54"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "54"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 54)
        self.assertTrue(re.search(r"d0n\.AIBody\.54:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 54 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.53", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 54, package `d0n.AIBody.54.var`, release `v54`", readme)
        self.assertIn("(version 54, release; Leon, voice 23:27-23:31", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T89", "## T90", "## T91", "## T92"):
            self.assertIn(step, proto)

    def test_release_notes_english(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v54**", notes)
        for part in ("d0n.AIBody.54.var", "Freeze Motion", "AI-Buddy.jpg", "Body position", "pose files are not changed",
                     "Idle poses from all pose files", "3 s", "8 s", "newest", "T89", "T92"):
            self.assertIn(part, notes)
