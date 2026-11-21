"""Version 39 (Leon, call 21.11.2026 15:59): the Question and Answer button is removed (see test_qa_button_removed);
otherwise the same contents as version 38.
"""
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
    def test_version_39_is_historical(self):
        """Historical: version 39 sources are gone after the v40 bump; consistency is test_version44."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version40.py").is_file())
        self.assertEqual(first_start.TEMPLATE, ROOT / "examples" / "scenes" / "AI-Buddy.json")
