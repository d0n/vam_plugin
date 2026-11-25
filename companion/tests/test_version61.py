"""Version 61 (comparison build against v60, 25.11.2026): IdlePoser attach guard during scene loads, Grok Bot bridge
(optional driver, opt-in setup task), own emotion keywords and gestures from yes / no (test_v61_items.py). Version
everywhere and English release notes."""
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
    def test_version_61_everywhere(self):
        self.assertEqual(__version__, "61")
        self.assertIn('PluginVersion = "61"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "61"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 61)
        self.assertTrue(re.search(r"d0n\.AIBody\.61:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 61 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.60", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 61, package `d0n.AIBody.61.var`, release `v61`", readme)
        self.assertIn("`ai.driver`", readme)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 61, release; comparison build against v60", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T114", "## T115", "## T116"):
            self.assertIn(step, proto)
        config = (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8")
        for key in ("`ai.driver`", "`ai.emotion.gestures`", "`ai.emotion.keywords`"):
            self.assertIn(key, config)
        bridge = (ROOT / "docs" / "GROK_BOT_BRIDGE.md").read_text(encoding="utf-8")
        for part in ("/api/bridge/events", "direct", "opt-in", "unchecked"):
            self.assertIn(part, bridge)
        self.assertIn("/api/bridge/events", (ROOT / "docs" / "REMOTE.md").read_text(encoding="utf-8"))

    def test_backlog_marks(self):
        backlog = (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8")
        self.assertIn("**done in version 61**", backlog)
        self.assertIn("**partly done in version 61**", backlog)
        self.assertIn("**Open:** auto-configuration of the local bot", backlog)

    def test_release_notes_english_without_personal_names(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v61**", notes)
        for part in ("d0n.AIBody.61.var", "Comparison build against v60", "AIBody Idle Movement", "Grok Bot bridge",
                     "ai.driver", "unchecked by default", "ai.emotion.keywords", "ai.emotion.gestures", "T114", "T116",
                     "not proven"):
            self.assertIn(part, notes)
        self.assertIsNone(re.search(r"\b(" + "Le" + "on|Don)\b", notes), "no personal names in public release notes")
