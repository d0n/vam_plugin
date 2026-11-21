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
    def test_version_43_is_historical(self):
        """Historical: version 43 sources are gone after the v44 bump; consistency is test_version45."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version45.py").is_file())
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 43, release; Leon, calls 20:04 and 20:05, release announced at 20:05): package `d0n.AIBody.43.var`, tag `v43`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T65", "## T66", "## T67", "## T68", "## T69"):
            self.assertIn(step, tp)
