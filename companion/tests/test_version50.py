"""Version 50 (Leon, call 22.11.2026 20:35, explicit go): reset / fresh-config fixes (test_v50_reset.py). Version
everywhere and English release notes."""
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
    def test_version_50_everywhere(self):
        self.assertEqual(__version__, "50")
        self.assertIn('PluginVersion = "50"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "50"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 50)
        self.assertTrue(re.search(r"d0n\.AIBody\.50:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 50 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.49", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 50, package `d0n.AIBody.50.var`, release `v50`", readme)
        self.assertIn("(version 50, release; Leon, call 20:35", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        self.assertIn("## T85", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))

    def test_release_notes_english(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v50**", notes)
        for part in ("d0n.AIBody.50.var", "clears the XAI API Token", "Language model", "Anna", "Marc", "(none)",
                     "Memory", "Speech-to-text", "Text-to-speech", "Mic enabled", "Push-to-talk interrupts speech", "T85"):
            self.assertIn(part, notes)
        fixed = notes.split("**Fixed")[1].split("Why the menus")[0]
        self.assertEqual(len(re.findall(r"^\d\. ", fixed, re.M)), 7)
