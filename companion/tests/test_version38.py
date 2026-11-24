"""Version 38 (Don, 21.11.2026): version bump of the character configuration wizard
and the AI-Buddy example scene already on main; no new features.
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
    def test_version_38_is_historical(self):
        """Historical: version 38 sources are gone after the v39 bump; consistency is test_version48."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version39.py").is_file())
        self.assertEqual(first_start.TEMPLATE, ROOT / "examples" / "scenes" / "AI-Buddy.json")
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
