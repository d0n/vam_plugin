"""Version 49 (Leon, call 22.11.2026 19:17, release go): everything on main since v48 - voice barge-in on by default
with echo protection, Language chooser (default German), setup notice, Apply Pose, Apply idle default pose, Body
position, tab Dollmaster (full port) and the CI path for assets/dollmaster. English release notes."""
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
    def test_version_49_everywhere(self):
        self.assertEqual(__version__, "49")
        self.assertIn('PluginVersion = "49"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "49"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 49)
        self.assertTrue(re.search(r"d0n\.AIBody\.49:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 49 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.48", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 49, package `d0n.AIBody.49.var`, release `v49`", readme)
        self.assertIn("(version 49, release; Leon, call 19:17", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for n in range(78, 85):
            self.assertIn(f"## T{n}", tp)

    def test_ci_builds_on_dollmaster_assets(self):
        wf = (ROOT / ".github" / "workflows" / "companion-windows.yml").read_text(encoding="utf-8")
        self.assertIn('"assets/dollmaster/**"', wf)

    def test_release_notes_english(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v49**", notes)
        for part in ("d0n.AIBody.49.var", "Voice barge-in", "echo", "Language", "German (de)", "Setup notice",
                     "Apply Pose", "Apply idle default pose", "Body position", "Tab Dollmaster", "Activate",
                     "expressions, breathing, idle motion and idle poses", "AIBody keeps speech", "VAMDeluxe",
                     "MIT", "98 MB", "T78-T84"):
            self.assertIn(part, notes)
        self.assertEqual(len(re.findall(r"^\d\. \*\*|^\d\. ", notes.split("**New**")[1].split("**Dollmaster notes**")[0],
                                        re.M)), 7)
