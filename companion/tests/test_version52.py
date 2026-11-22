"""Version 52 (Leon, call 22.11.2026 20:47-20:48, explicit go): pose commands / Apply Pose / twitching / pose menu race
(test_v52_poses.py). Released as v52 (22.11.2026)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_52_is_historical(self):
        """Historical: version 52 sources are gone after the v53 bump; consistency is test_version53."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version53.py").is_file())
        self.assertIn("(version 52, release; Leon, call 20:47-20:48", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        self.assertIn("## T87", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
