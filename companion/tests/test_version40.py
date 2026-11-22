"""Version 40 (Leon, 21.11.2026): wizard question, persona starters, quiet log, AIBody Companion installer."""
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
    def test_version_40_is_historical(self):
        """Historical: version 40 sources are gone after the v41 bump; consistency is test_version46."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version41.py").is_file())
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 40, release; Leon, calls 16:06-16:16): package `d0n.AIBody.40.var`, tag `v40`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T48", "## T49", "## T50", "## T51"):
            self.assertIn(step, tp)
