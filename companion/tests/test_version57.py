"""Version 57 (Leon, voice 24.11.2026 15:57, explicit go): a failing idle pose is dropped from the pool at once and the
next one is loaded right away. Released as v57 (24.11.2026)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_57_is_historical(self):
        """Historical: version 57 sources are gone after the v58 bump; consistency is test_version58."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version58.py").is_file())
        self.assertIn("(version 57, release; Leon, voice 24.11.2026 15:57", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        self.assertIn("## T102", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
