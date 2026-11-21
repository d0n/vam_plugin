"""Version 45 (Leon, 21.11.2026 21:25 and 22:25): the setup removes older d0n.AIBody.<n>.var only after the install
succeeded and the new package is in place (v44 lost the package on a failed / cancelled install), without an option;
a companion that cannot be ended stops the setup before changes. The item tests are in test_package_after_install.py."""
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
    def test_version_45_everywhere(self):
        self.assertEqual(__version__, "45")
        self.assertIn('PluginVersion = "45"', source("AIBody.cs"))
        self.assertIn('version = "45"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 45)
        self.assertTrue(re.search(r"d0n\.AIBody\.45:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 45 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 45, package `d0n.AIBody.45.var`, release `v45`", readme)
        self.assertNotIn("option **Remove older AIBody packages**", readme)
        start = readme[readme.index("## Getting started"):readme.index("### For developers")]
        for part in ("AIBody Companion Setup.exe", "More info", "Run anyway", "Start menu", "Start with Windows",
                     "127.0.0.1", "Add Plugin"):
            self.assertIn(part, start)
        self.assertNotIn("python -m", start)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 45, release; Leon, calls 21:25 and 22:25, release approved at 22:26): package `d0n.AIBody.45.var`, tag `v45`", spec)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## T74", tp)

    def test_release_notes(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v45**", notes)
        self.assertNotIn("<next>", notes)
        self.assertNotIn("Keep **Remove older AIBody packages** checked", notes)
        for part in ("d0n.AIBody.45.var", "failed or was cancelled", "T74"):
            self.assertIn(part, notes)
