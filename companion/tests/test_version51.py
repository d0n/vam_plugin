"""Version 51 (Leon, call 22.11.2026 20:38-20:58, explicit go): idle poses random of all poses, idle timer sliders
30 / 300 s (30-18000 s), no empty dropdown after Reset to Default (test_v51_idle.py, test_v51_choosers.py). Released as
v51 (22.11.2026)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_51_is_historical(self):
        """Historical: version 51 sources are gone after the v52 bump; consistency is test_version52."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version52.py").is_file())
        self.assertIn("(version 51, release; Leon, call 20:38-20:58", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        self.assertIn("## T86", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
