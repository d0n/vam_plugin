"""Version 59 (explicit go, 24.11.2026 23:58): one idle pose interval, fixed English built-in pose commands, one
failover for every pose command, no German phrases (test_v59_items.py). Released as v59 (25.11.2026)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_59_is_historical(self):
        """Historical: version 59 sources are gone after the v60 bump; consistency is test_version60."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version60.py").is_file())
        self.assertIn("(version 59, release; explicit go 24.11.2026 23:58)", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T107", "## T108", "## T109", "## T110"):
            self.assertIn(step, proto)
        self.assertIn("idle_pose_interval_s", (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8"))
