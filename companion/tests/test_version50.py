"""Version 50 (Don, call 22.11.2026 20:35, explicit go): reset / fresh-config fixes (test_v50_reset.py). Released as
v50 (22.11.2026)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_50_is_historical(self):
        """Historical: version 50 sources are gone after the v51 bump; consistency is test_version51."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version51.py").is_file())
        self.assertIn("(version 50, release; Don, call 20:35", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        self.assertIn("## T85", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
