"""Version 39 (Leon, call 21.11.2026 15:59): the Question and Answer button is removed (see test_qa_button_removed);
otherwise the same contents as version 38.
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
    def test_version_39_everywhere(self):
        self.assertEqual(__version__, "39")
        self.assertIn('PluginVersion = "39"', source("AIBody.cs"))
        self.assertIn('version = "39"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 39)
        self.assertTrue(re.search(r"d0n\.AIBody\.39:", first_start.TEMPLATE.read_text()))
        self.assertEqual(first_start.TEMPLATE, ROOT / "examples" / "scenes" / "AI-Buddy.json")
        self.assertIn("AIBody companion app 39 (example)",
                      (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")

    def test_docs_name_version_39(self):
        self.assertIn("Status: version 39, package `d0n.AIBody.39.var`, release `v39`",
                      (ROOT / "README.md").read_text(encoding="utf-8"))
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 39, release): package `d0n.AIBody.39.var`, tag `v39`", spec)
        self.assertIn("now version 39;", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
