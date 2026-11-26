"""Version 67 (26.11.2026, on top of v66): v66 did not load on Don's PC because VaM had plugins of d0n.AIBody.66 set to "always
denied" (VaM log + AddonPackagesUserPrefs); the companion now warns about it (read-only). Reload Plugin keeping the plugin's
settings is NOT in v67 (cause not confirmed). Version 67 everywhere; the plugin passes the VaM-limits compile check."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__, package_prefs
from aibody_companion import setup as first_start

from .test_plugin_menu import method_body
from . import test_version35 as v35

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
HARNESS = Path(__file__).parent / "csharp_reload_harness" / "Program.cs"


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class VersionTests(TestCase):
    def test_version_67_everywhere(self):
        self.assertEqual(__version__, "67")
        self.assertIn('PluginVersion = "67"', src("AIBody.cs"))
        self.assertIn('version = "67"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 67)
        self.assertTrue(re.search(r"d0n\.AIBody\.67:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 67 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 67, package `d0n.AIBody.67.var`, release `v67`", readme)
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.66.var", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_release_notes(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        for part in ("**AIBody v67**", "d0n.AIBody.67.var", "always been denied plugin loading", "User Prefs",
                     "Not in this release", "T125"):
            self.assertIn(part, notes)
        self.assertNotIn("Le" + "on", notes)
        self.assertIn("## T125 ", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
        self.assertIn("(version 67, release; on top of v66)", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))


class CslistTests(TestCase):
    """Regression guard: every plugin source is in AIBody.cslist exactly once, every listed file exists, the MVRScript file last."""

    def test_cslist_matches_the_sources(self):
        listed = [l.strip() for l in src("AIBody.cslist").splitlines() if l.strip()]
        self.assertEqual(len(listed), len(set(listed)), "no file twice")
        for name in listed:
            self.assertTrue((SRC / name).is_file(), name)
        on_disk = sorted(p.name for p in SRC.glob("*.cs"))
        self.assertEqual(sorted(listed), on_disk)
        self.assertEqual(listed[-1], "AIBody.cs")

    def test_no_csharp_7_constructs_in_the_plugin(self):
        """VaM compiles C# 6 (tools/check_plugin.py also builds with LangVersion 6); a cheap text guard on top."""
        bad = re.compile(r"\bout var\b|\bis not\b|\bis null\b|\bswitch\s*\{|\bdefault\s*[;,)]|\b_\s*=")
        for path in SRC.glob("*.cs"):
            # one pass over comments, verbatim / normal strings and char literals, so "//" in a string or '"' in a char
            # literal cannot confuse the next rule
            token = re.compile(r'//[^\n]*|/\*.*?\*/|@"(?:""|[^"])*"|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\])\'', re.S)
            code = token.sub(' ', path.read_text(encoding="utf-8"))
            m = bad.search(code)
            self.assertIsNone(m, f"{path.name}: {m.group(0) if m else ''}")

    def test_compile_check_uses_vams_limits(self):
        check = (ROOT / "tools" / "check_plugin.py").read_text(encoding="utf-8")
        self.assertIn("<LangVersion>6</LangVersion>", check)
        self.assertIn("<TargetFramework>net35</TargetFramework>", check)


class PackagePrefsTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "AddonPackages").mkdir()
        (self.root / "AddonPackagesUserPrefs").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def prefs(self, version, enabled, disabled):
        (self.root / "AddonPackagesUserPrefs" / f"d0n.AIBody.{version}.prefs").write_text(json.dumps(
            {"pluginsAlwaysEnabled": enabled, "pluginsAlwaysDisabled": disabled, "ignoreMissingDependencyErrors": "false"}), encoding="utf-8")

    def var(self, version):
        (self.root / "AddonPackages" / f"d0n.AIBody.{version}.var").write_bytes(b"PK")

    def test_dons_case_is_found(self):
        self.var(66)
        self.prefs(65, "true", "false")
        self.prefs(66, "false", "true")
        self.assertEqual(package_prefs.denied_installed(self.root), ["d0n.AIBody.66"])
        text = package_prefs.warning(self.root)
        self.assertIn("d0n.AIBody.66", text)
        self.assertIn("User Prefs", text)

    def test_allowed_missing_broken_or_not_installed_is_quiet(self):
        self.var(67)
        self.assertIsNone(package_prefs.warning(self.root), "no prefs file yet (VaM asks)")
        self.prefs(67, "true", "false")
        self.assertIsNone(package_prefs.warning(self.root))
        (self.root / "AddonPackagesUserPrefs" / "d0n.AIBody.67.prefs").write_text("{broken", encoding="utf-8")
        self.assertIsNone(package_prefs.warning(self.root))
        self.prefs(60, "false", "true")
        self.assertIsNone(package_prefs.warning(self.root), "old package not installed any more")
        self.assertIsNone(package_prefs.warning(self.root / "nope"))

    def test_read_only_and_wired_into_the_start(self):
        code = (ROOT / "companion" / "aibody_companion" / "package_prefs.py").read_text(encoding="utf-8")
        self.assertNotIn("write_text", code)
        self.assertNotIn("open(", code)
        cli = (ROOT / "companion" / "aibody_companion" / "cli.py").read_text(encoding="utf-8")
        self.assertIn("package_prefs.warning(cfg.vam_root)", cli)
