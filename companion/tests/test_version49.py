"""Version 49 (Don, call 22.11.2026 19:17, release go): everything on main since v48 - voice barge-in on by default
with echo protection, Language chooser (default German), setup notice, Apply Pose, Apply idle default pose, Body
position, tab Dollmaster (full port) and the CI path for assets/dollmaster. English release notes. Released as v49 (22.11.2026)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__
from aibody_companion import setup as first_start

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


class VersionTests(TestCase):
    def test_version_49_is_historical(self):
        """Historical: version 49 sources are gone after the v50 bump; consistency is test_version50."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version50.py").is_file())

    def test_ci_builds_on_dollmaster_assets(self):
        wf = (ROOT / ".github" / "workflows" / "companion-windows.yml").read_text(encoding="utf-8")
        self.assertIn('"assets/dollmaster/**"', wf)
