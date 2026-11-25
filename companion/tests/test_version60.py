"""Version 60 (approved plan, go 25.11.2026): idle movement with MacGruber's IdlePoser on the AI character
(test_v60_idle_movement.py). Released as v60 (25.11.2026)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_60_is_historical(self):
        """Historical: version 60 sources are gone after the v61 bump; consistency is test_version61."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version61.py").is_file())
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 60, release; approved plan, go 25.11.2026)", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T111", "## T112", "## T113"):
            self.assertIn(step, proto)
        self.assertIn("idle_movement_liveliness", (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8"))
        self.assertIn("IdlePoser", (ROOT / "docs" / "CREDITS.md").read_text(encoding="utf-8"))
