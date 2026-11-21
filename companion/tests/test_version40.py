"""Version 40 (Leon, 21.11.2026): wizard question, persona starters, quiet log, AIBody Companion installer."""
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
    def test_version_40_everywhere(self):
        self.assertEqual(__version__, "40")
        self.assertIn('PluginVersion = "40"', source("AIBody.cs"))
        self.assertIn('version = "40"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 40)
        self.assertTrue(re.search(r"d0n\.AIBody\.40:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 40 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 40, package `d0n.AIBody.40.var`, release `v40`", readme)
        start = readme[readme.index("## Getting started"):readme.index("### For developers")]
        for part in ("AIBody Companion Setup.exe", "More info", "Run anyway", "Start menu", "Start with Windows",
                     "127.0.0.1", "Add Plugin"):
            self.assertIn(part, start)
        self.assertNotIn("python -m", start)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 40, release; Leon, calls 16:06-16:16): package `d0n.AIBody.40.var`, tag `v40`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("## T48", "## T49", "## T50", "## T51"):
            self.assertIn(step, tp)
