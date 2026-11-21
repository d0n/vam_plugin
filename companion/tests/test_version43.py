"""Version 43 (Leon, 21.11.2026 20:04-20:05): louder test tone, update notice, uninstall removes our VARs, speech_ended
"completed". The item tests are in test_version43_items.py and test_test_tone_level.py."""
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
    def test_version_43_everywhere(self):
        self.assertEqual(__version__, "43")
        self.assertIn('PluginVersion = "43"', source("AIBody.cs"))
        self.assertIn('version = "43"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 43)
        self.assertTrue(re.search(r"d0n\.AIBody\.43:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 43 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 43, package `d0n.AIBody.43.var`, release `v43`", readme)
        start = readme[readme.index("## Getting started"):readme.index("### For developers")]
        for part in ("AIBody Companion Setup.exe", "More info", "Run anyway", "Start menu", "Start with Windows",
                     "127.0.0.1", "Add Plugin"):
            self.assertIn(part, start)
        self.assertNotIn("python -m", start)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 43, release; Leon, calls 20:04 and 20:05, release announced at 20:05): package `d0n.AIBody.43.var`, tag `v43`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T65", "## T66", "## T67", "## T68", "## T69"):
            self.assertIn(step, tp)

    def test_release_notes(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v43**", notes)
        self.assertNotIn("<next>", notes)
        for part in ("+6 dB", "Update notice", "d0n.AIBody.<number>.var", "completed", "T65 to T69"):
            self.assertIn(part, notes)
