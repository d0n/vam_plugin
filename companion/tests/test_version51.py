"""Version 51 (Leon, call 22.11.2026 20:38-20:58, explicit go): idle poses random of all poses, idle timer sliders
30 / 300 s (30-18000 s), no empty dropdown after Reset to Default (test_v51_idle.py, test_v51_choosers.py). Version
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
    def test_version_51_everywhere(self):
        self.assertEqual(__version__, "51")
        self.assertIn('PluginVersion = "51"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "51"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 51)
        self.assertTrue(re.search(r"d0n\.AIBody\.51:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 51 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.50", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 51, package `d0n.AIBody.51.var`, release `v51`", readme)
        self.assertIn("(version 51, release; Leon, call 20:38-20:58", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        self.assertIn("## T86", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))

    def test_release_notes_english(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v51**", notes)
        for part in ("d0n.AIBody.51.var", "all", "never the same pose twice in a row", "Idle pose min wait (s)",
                     "Idle pose max wait (s)", "30 s", "300 s (5 min)", "30 to 18000 s (300 min)", "value field",
                     "Dollmaster", "two poses", "Reset to Default", "empty dropdown", "T86"):
            self.assertIn(part, notes)
