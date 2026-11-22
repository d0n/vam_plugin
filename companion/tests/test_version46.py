"""Version 46 (Leon, 22.11.2026 04:02-04:17): speech loudness. The shipped scene's head audio had minDistance 0.04 m
(Unity's logarithmic rolloff: about -28 dB at 1 m); now 2 m, plus the 'Full volume distance (m)' slider and Speech
volume in percent (0-1000, default 100; Leon 04:16). The item tests are in test_speech_loudness.py."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__
from aibody_companion import setup as first_start

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class VersionTests(TestCase):
    def test_version_46_everywhere(self):
        self.assertEqual(__version__, "46")
        self.assertIn('PluginVersion = "46"', source("AIBody.cs"))
        self.assertIn('version = "46"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 46)
        self.assertTrue(re.search(r"d0n\.AIBody\.46:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 46 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        # Leon 04:16/04:17: v46, not v47
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.47", (ROOT / f).read_text(encoding="utf-8"))

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 46, package `d0n.AIBody.46.var`, release `v46`", readme)
        start = readme[readme.index("## Getting started"):readme.index("### For developers")]
        for part in ("AIBody Companion Setup.exe", "More info", "Run anyway", "Start menu", "Start with Windows",
                     "127.0.0.1", "Add Plugin"):
            self.assertIn(part, start)
        self.assertNotIn("python -m", start)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 46, release; Leon, 04:02-04:17", spec)
        self.assertIn("package `d0n.AIBody.46.var`, tag `v46`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## T75", tp)

    def test_release_notes(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v46**", notes)
        self.assertNotIn("<next>", notes)
        for part in ("d0n.AIBody.46.var", "Full volume distance (m)", "Speech volume (%)", "T75"):
            self.assertIn(part, notes)
