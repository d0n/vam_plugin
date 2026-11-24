"""Version 53 (Don, call 22.11.2026 20:49 / 20:57, explicit go): expressions, Show expression, button regrouping
(test_v53_expressions.py). Released as v53 (22.11.2026)."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(TestCase):
    def test_version_53_is_historical(self):
        """Historical: version 53 sources are gone after the v54 bump; consistency is test_version54."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version54.py").is_file())
        self.assertIn("(version 53, release; Don, call 20:49 / 20:57", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        self.assertIn("## T88", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
