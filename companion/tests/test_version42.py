"""Version 42 (Don, 21.11.2026 18:27 and 18:33): pose menu (choosing applies, Add Pose with the file browser, Delete
Pose, Reset poses), AIBody on 'Client' driving 'AI' in his scene, version check, realtime answer after a tool call,
scrollable Voice menu. The item tests are in test_version42_items.py."""
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
    def test_version_42_is_historical(self):
        """Historical: version 42 sources are gone after the v43 bump; consistency is test_version48."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version43.py").is_file())
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 42, release; Don, 18:27 and 18:33, GO for v42 at 18:33 once everything is done): package `d0n.AIBody.42.var`, tag `v42`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T59", "## T60", "## T61", "## T62", "## T63", "## T64"):
            self.assertIn(step, tp)
