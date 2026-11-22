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
    def test_version_46_is_historical(self):
        """Historical: version 46 sources are gone after the v47 bump; consistency is test_version48."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version47.py").is_file())

    def test_docs(self):
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 46, release; Leon, 04:02-04:17", spec)
        self.assertIn("package `d0n.AIBody.46.var`, tag `v46`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## T75", tp)
