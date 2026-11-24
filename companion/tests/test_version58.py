"""Version 58 (Don, voice 24.11.2026 16:07-16:09, explicit go): pose commands inside a sentence, substitute pose for
built-in commands, no empty dropdown (test_v58_items.py). Released as v58 (24.11.2026)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_58_is_historical(self):
        """Historical: version 58 sources are gone after the v59 bump; consistency is test_version59."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version59.py").is_file())
        self.assertIn("(version 58, release; Don, voice 24.11.2026 16:07-16:09", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T103", "## T104", "## T105", "## T106"):
            self.assertIn(step, proto)
