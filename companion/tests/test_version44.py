"""Version 44 (Leon, 21.11.2026 20:39-21:09): the setup installs the package and removes older ones, reports an existing
install, closes a running companion, writes a log; Speech volume up to 3. The item tests are in test_version44_items.py."""
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
    def test_version_44_is_historical(self):
        """Historical: version 44 sources are gone after the v45 bump; consistency is test_version48."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version47.py").is_file())

    def test_docs(self):
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 44, release; Leon, calls 20:39-21:09, release approved at 21:01): package `d0n.AIBody.44.var`, tag `v44`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T70", "## T71", "## T72", "## T73"):
            self.assertIn(step, tp)
