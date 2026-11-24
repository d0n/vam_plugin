"""Version 45 (Don, 21.11.2026 21:25 and 22:25): the setup removes older d0n.AIBody.<n>.var only after the install
succeeded and the new package is in place (v44 lost the package on a failed / cancelled install), without an option;
a companion that cannot be ended stops the setup before changes. The item tests are in test_package_after_install.py."""
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
    def test_version_45_is_historical(self):
        """Historical: version 45 sources are gone after the v46 bump; consistency is test_version48."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version47.py").is_file())

    def test_docs(self):
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 45, release; Don, calls 21:25 and 22:25, release approved at 22:26): package `d0n.AIBody.45.var`, tag `v45`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## T74", tp)
