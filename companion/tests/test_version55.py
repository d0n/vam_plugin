"""Version 55 (Leon, 23.11.2026, explicit go): mute / unmute by voice (name-independent) and the menu toggle
"Mute AI (stop talking and listening)" (test_v55_mute.py). Released as v55 (23.11.2026)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_55_is_historical(self):
        """Historical: version 55 sources are gone after the v56 bump; consistency is test_version56."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version56.py").is_file())
        self.assertIn("(version 55, release; Leon 23.11.2026", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T93", "## T94", "## T95", "## T96"):
            self.assertIn(step, proto)
