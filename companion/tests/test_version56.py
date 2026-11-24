"""Version 56 (Don, voice 24.11.2026 15:27-15:30, explicit go): pose changes keep her place, companion pose commands,
Idle Poser, Reset with Dollmaster, realtime without VaM (test_v56_pose_guard.py). Released as v56 (24.11.2026)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_56_is_historical(self):
        """Historical: version 56 sources are gone after the v57 bump; consistency is test_version57."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version57.py").is_file())
        self.assertIn("(version 56, release; Don, voice 24.11.2026 15:27-15:30", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T97", "## T98", "## T99", "## T100", "## T101"):
            self.assertIn(step, proto)
