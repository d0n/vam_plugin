"""Version 62 (test build, 25.11.2026): MacGruber IdlePoser idle movement excluded at build time to isolate the
Always-Allow crash. Released as v62 (25.11.2026); version 63 compiles the code in again as an optional toggle that is
off by default (test_version63.py)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_62_is_historical(self):
        """Historical: version 62 sources are gone after the v63 bump; consistency is test_version63."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version63.py").is_file())
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 62, release; test build to isolate the Always-Allow crash)", spec)
        self.assertIn("## T117", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
        switch = (ROOT / "docs" / "IDLEPOSER_BUILD_SWITCH.md").read_text(encoding="utf-8")
        for part in ("AIBODY_IDLEPOSER", "Version 62", "8426d3b"):
            self.assertIn(part, switch)
