"""Version 55 (Leon, 23.11.2026, explicit go): mute / unmute by voice (name-independent) and the menu toggle
"Mute AI (stop talking and listening)" (test_v55_mute.py). Version everywhere and English release notes."""
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
    def test_version_55_everywhere(self):
        self.assertEqual(__version__, "55")
        self.assertIn('PluginVersion = "55"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "55"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 55)
        self.assertTrue(re.search(r"d0n\.AIBody\.55:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 55 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.54", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 55, package `d0n.AIBody.55.var`, release `v55`", readme)
        self.assertIn("Mute AI (stop talking and listening)", readme)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 55, release; Leon 23.11.2026", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T93", "## T94", "## T95", "## T96"):
            self.assertIn(step, proto)
        self.assertIn("`mute`", (ROOT / "protocol" / "PROTOCOL.md").read_text(encoding="utf-8"))

    def test_release_notes_english(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v55**", notes)
        for part in ("d0n.AIBody.55.var", "Mute AI (stop talking and listening)", "shut up", "halt's Maul",
                     "halt die Klappe", "sei still", "sprich mit mir", "speak again", "go ahead talking",
                     "Reset to Default", "T93", "T96"):
            self.assertIn(part, notes)
