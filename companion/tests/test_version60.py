"""Version 60 (approved plan, go 25.11.2026): idle movement with MacGruber's IdlePoser on the AI character
(test_v60_idle_movement.py). Version everywhere and English release notes."""
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
    def test_version_60_everywhere(self):
        self.assertEqual(__version__, "60")
        self.assertIn('PluginVersion = "60"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "60"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 60)
        self.assertTrue(re.search(r"d0n\.AIBody\.60:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 60 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.59", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 60, package `d0n.AIBody.60.var`, release `v60`", readme)
        self.assertIn("**Idle movement liveliness**", readme)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 60, release; approved plan, go 25.11.2026)", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T111", "## T112", "## T113"):
            self.assertIn(step, proto)
        self.assertIn("idle_movement_liveliness", (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8"))
        self.assertIn("IdlePoser", (ROOT / "docs" / "CREDITS.md").read_text(encoding="utf-8"))
        self.assertIn("CC BY-SA", (ROOT / "docs" / "CREDITS.md").read_text(encoding="utf-8"))

    def test_release_notes_english_without_personal_names(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v60**", notes)
        for part in ("d0n.AIBody.60.var", "MacGruber.IdlePoser.9", "Idle movement", "Idle movement liveliness",
                     "AI character only", "CC BY-SA", "T111", "T113"):
            self.assertIn(part, notes)
        self.assertIsNone(re.search(r"\b(" + "Le" + "on|Don)\b", notes),
                          "no personal names in public release notes")
