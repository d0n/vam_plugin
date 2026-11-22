"""Version 41 (Leon, 21.11.2026 17:01-17:27): installer VaM folder, Reset to Default, AIBody on BryanGosling, speech audio
fix, all xAI voices, every persona, Apply pose command, right column, no spoken tool calls."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__
from aibody_companion import setup as first_start

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class VersionTests(TestCase):
    def test_version_41_is_historical(self):
        """Historical: version 41 sources are gone after the v42 bump; consistency is test_version46."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version42.py").is_file())
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 41, release; Leon, calls 17:01-17:27, GO for v41 at 17:19): package `d0n.AIBody.41.var`, tag `v41`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T52", "## T53", "## T54", "## T55", "## T56", "## T57", "## T58"):
            self.assertIn(step, tp)

    def test_scene_plugin_on_bryan(self):
        scene = json.loads((ROOT / "examples" / "scenes" / "AI-Buddy.json").read_text(encoding="utf-8"))
        holders = []
        for atom in scene["atoms"]:
            for st in atom.get("storables", []):
                if st.get("id") == "PluginManager" and st.get("plugins"):
                    holders.append((atom["id"], dict(st["plugins"])))
        # version 42 (Leon 18:27): his scene, AIBody on "Client" (test_version42_items)
        self.assertEqual([h for h, _ in holders], ["Client"])
