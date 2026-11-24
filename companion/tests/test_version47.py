"""Version 47 (Don, 22.11.2026 12:17-12:25): fixes the v46 regression (speech did not start, only the test tone was
heard, sound worse than v45) by going back to v45's head audio handling, removes the Breath morph / Breath1 boxes and
always packs the scene thumbnail next to the scene. The item tests are in test_v47_regression.py. Released as v47 (22.11.2026)."""
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
    def test_version_47_is_historical(self):
        """Historical: version 47 sources are gone after the v48 bump; consistency is test_version48."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version48.py").is_file())

    def test_docs(self):
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 47; Don, 12:17-12:25", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## T76", tp)
