"""Version 54 (Leon, voice 22.11.2026 23:27-23:31, explicit go): scene without Freeze state, thumbnail pair, Body
position, idle pool, speech backlog (test_v54_items.py). Released as v54 (22.11.2026)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_54_is_historical(self):
        """Historical: version 54 sources are gone after the v55 bump; consistency is test_version55."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version55.py").is_file())
        self.assertIn("(version 54, release; Leon, voice 23:27-23:31", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T89", "## T90", "## T91", "## T92"):
            self.assertIn(step, proto)
