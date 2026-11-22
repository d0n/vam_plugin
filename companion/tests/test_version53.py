"""Version 53 (Leon, call 22.11.2026 20:49 / 20:57, explicit go): expressions, Show expression, button regrouping
(test_v53_expressions.py). Version everywhere and English release notes."""
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
    def test_version_53_everywhere(self):
        self.assertEqual(__version__, "53")
        self.assertIn('PluginVersion = "53"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "53"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 53)
        self.assertTrue(re.search(r"d0n\.AIBody\.53:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 53 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.52", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 53, package `d0n.AIBody.53.var`, release `v53`", readme)
        self.assertIn("(version 53, release; Leon, call 20:49 / 20:57", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        self.assertIn("## T88", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))

    def test_release_notes_english(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v53**", notes)
        for part in ("d0n.AIBody.53.var", "Auto Expressions", "Show expression", "neutral", "Reset expression",
                     "Reload expressions (expressions.json)", "Reload Config JSON", "Reload config files", "T88"):
            self.assertIn(part, notes)
