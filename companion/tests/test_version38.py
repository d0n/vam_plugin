"""Version 38 (Leon, 21.11.2026): version bump of the character configuration wizard
and the AI-Buddy example scene already on main; no new features.
"""
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
    def test_version_38_everywhere(self):
        self.assertEqual(__version__, "38")
        self.assertIn('PluginVersion = "38"', source("AIBody.cs"))
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 38)
        self.assertTrue(re.search(r"d0n\.AIBody\.38:", first_start.TEMPLATE.read_text()))
        self.assertEqual(first_start.TEMPLATE, ROOT / "examples" / "scenes" / "AI-Buddy.json")
        self.assertIn("AIBody companion app 38 (example)",
                      (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
