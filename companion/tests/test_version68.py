"""Version 68 (26.11.2026, on top of v67): VaM crashed in its script compiler (mono.dll access violation in
TypeBuilder.CreateType) after "Allow" for every AIBody build that compiled a C# enum (v60, v61, v63, v67); the enum-free builds
did not. OriginReset.Verdict is int constants now and no compiled plugin file declares an enum."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__
from aibody_companion import setup as first_start

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def code(text: str) -> str:
    """C# without comments, strings and char literals."""
    pat = re.compile(r'//[^\n]*|/\*.*?\*/|@"(?:[^"]|"")*"|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'', re.S)
    return pat.sub(" ", text)


def compiled_files() -> list[Path]:
    names = [l.strip() for l in (SRC / "AIBody.cslist").read_text(encoding="utf-8").splitlines() if l.strip()]
    return [SRC / n for n in names]


class VersionTests(TestCase):
    def test_version_68_everywhere(self):
        self.assertEqual(__version__, "68")
        self.assertIn('PluginVersion = "68"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "68"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 68)
        self.assertTrue(re.search(r"d0n\.AIBody\.68:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 68 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 68, package `d0n.AIBody.68.var`, release `v68`", readme)
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        for s in ("Release notes of version 68", "crashed right after allowing", "T126"):
            self.assertIn(s, notes)
        self.assertIn("## T126", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))


class NoEnumTests(TestCase):
    def test_no_enum_in_any_compiled_file(self):
        files = compiled_files()
        self.assertGreater(len(files), 40)
        for f in files:
            m = re.search(r"\benum\s+[A-Za-z_]", code(f.read_text(encoding="utf-8")))
            self.assertIsNone(m, f"{f.name} declares an enum (VaM's compiler crashed on it in v60/v61/v63/v67)")

    def test_guard_catches_an_enum(self):
        self.assertIsNotNone(re.search(r"\benum\s+[A-Za-z_]", code("public static class X { public enum V { A, B } }")))
        self.assertIsNone(re.search(r"\benum\s+[A-Za-z_]", code('// enum Foo\nvar s = "enum Bar";')))

    def test_origin_reset_uses_int_results(self):
        rr = code((SRC / "RootReset.cs").read_text(encoding="utf-8"))
        for s in ("public const int Ok = 0;", "public const int Tiny = 1;", "public const int Absurd = 2;", "public static int Delta("):
            self.assertIn(s, rr)
        pc = (SRC / "PoseController.cs").read_text(encoding="utf-8")
        self.assertIn("int v = OriginReset.Delta(", pc)
        self.assertIn("v == OriginReset.Absurd", pc)
        self.assertNotIn("Verdict.", pc)
