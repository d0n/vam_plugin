"""Version 58 (Don, voice 24.11.2026 16:07-16:09, explicit go): pose commands inside a sentence, substitute pose for
built-in commands, no empty dropdown (test_v58_items.py). Version everywhere and English release notes."""
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
    def test_version_58_everywhere(self):
        self.assertEqual(__version__, "58")
        self.assertIn('PluginVersion = "58"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "58"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 58)
        self.assertTrue(re.search(r"d0n\.AIBody\.58:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 58 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.57", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 58, package `d0n.AIBody.58.var`, release `v58`", readme)
        self.assertIn("version 58: `please sit down now` works too", readme)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 58, release; Don, voice 24.11.2026 16:07-16:09", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T103", "## T104", "## T105", "## T106"):
            self.assertIn(step, proto)

    def test_release_notes_english(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v58**", notes)
        for part in ("d0n.AIBody.58.var", "please sit down now", "kannst du dich hinsetzen", "don't sit down",
                     "substitute", "Not set", "None", "Reset to Default", "T103", "T106"):
            self.assertIn(part, notes)
