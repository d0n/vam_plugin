"""Version 61 (comparison build against v60, 25.11.2026): IdlePoser attach guard during scene loads, Grok Bot bridge
(optional driver, opt-in setup task), own emotion keywords and gestures from yes / no (test_v61_items.py). Released as
v61 (25.11.2026)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_61_is_historical(self):
        """Historical: version 61 sources are gone after the v62 bump; consistency is test_version62."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version62.py").is_file())
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 61, release; comparison build against v60", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T114", "## T115", "## T116"):
            self.assertIn(step, proto)
        config = (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8")
        for key in ("`ai.driver`", "`ai.emotion.gestures`", "`ai.emotion.keywords`"):
            self.assertIn(key, config)
        self.assertIn("/api/bridge/events", (ROOT / "docs" / "GROK_BOT_BRIDGE.md").read_text(encoding="utf-8"))
        backlog = (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8")
        self.assertIn("**done in version 61**", backlog)
