"""Version 62 (test build, 25.11.2026): MacGruber IdlePoser idle movement excluded at build time to isolate the
Always-Allow crash. The code stays in the repository behind #if AIBODY_IDLEPOSER; version everywhere and English
release notes."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__
from aibody_companion import setup as first_start

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
SYMBOL = "AIBODY_IDLEPOSER"


class VersionTests(TestCase):
    def test_version_62_everywhere(self):
        self.assertEqual(__version__, "62")
        self.assertIn('PluginVersion = "62"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "62"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 62)
        self.assertTrue(re.search(r"d0n\.AIBody\.62:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 62 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.61", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 62, package `d0n.AIBody.62.var`, release `v62`", readme)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 62, release; test build to isolate the Always-Allow crash)", spec)
        self.assertIn("## T117", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
        switch = (ROOT / "docs" / "IDLEPOSER_BUILD_SWITCH.md").read_text(encoding="utf-8")
        for part in (SYMBOL, "AIBody.cslist", "IdleMovement.cs", "IdlePoserLink.cs", "MacGruber.IdlePoser.9"):
            self.assertIn(part, switch)

    def test_release_notes_english_without_personal_names(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v62**", notes)
        self.assertIn("Test build: MacGruber IdlePoser idle movement excluded at build time to isolate the Always-Allow "
                      "crash; re-enable by defining AIBODY_IDLEPOSER and re-adding the two files to AIBody.cslist.", notes)
        for part in ("d0n.AIBody.62.var", "AI-Buddy.jpg", "T117"):
            self.assertIn(part, notes)
        self.assertIsNone(re.search(r"\b(" + "Le" + "on|Don)\b", notes), "no personal names in public release notes")


class IdlePoserExcludedAtBuildTimeTests(TestCase):
    def test_files_stay_but_are_not_compiled(self):
        cslist = (SRC / "AIBody.cslist").read_text(encoding="utf-8").split()
        for name in ("IdleMovement.cs", "IdlePoserLink.cs"):
            self.assertTrue((SRC / name).is_file(), name)
            self.assertNotIn(name, cslist)
            lines = [ln.strip() for ln in (SRC / name).read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
            first = next(ln for ln in lines if not ln.startswith("//"))
            self.assertEqual(first, "#if " + SYMBOL, name)
            self.assertEqual(lines[-1], "#endif", name)

    def test_symbol_defined_nowhere_in_the_plugin(self):
        for path in sorted(SRC.glob("*.cs")):
            self.assertNotIn("#define " + SYMBOL, path.read_text(encoding="utf-8"), path.name)

    def test_body_uses_idleposer_types_only_inside_the_symbol(self):
        """Outside #if AIBODY_IDLEPOSER, Body.cs names no IdlePoser type or member."""
        outside, depth = [], 0
        for line in (SRC / "Body.cs").read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("#if " + SYMBOL):
                depth += 1
                continue
            if depth and s.startswith("#if"):
                depth += 1
                continue
            if depth and s.startswith("#endif"):
                depth -= 1
                continue
            if not depth:
                outside.append(line)
        text = "\n".join(outside)
        for word in ("IdlePoserLink", "IdleMovementGate", "IdleMovementPlan", "IdleMovementInputs", "IdleMovementStep",
                     "IdlePart", "_poser", "_idleMove", "UpdateIdleMovement", "StartIdleMovement", "StopIdleMovement",
                     "IdleMovementInfo", '"idle_movement'):
            self.assertNotIn(word, text, word)

    def test_no_idleposer_dependency(self):
        meta = json.loads((ROOT / "packaging" / "meta.json").read_text(encoding="utf-8"))
        self.assertFalse([n for n in meta.get("dependencies", {}) if "IdlePoser" in n])
        self.assertNotIn("IdlePoser", (ROOT / "examples" / "scenes" / "AI-Buddy.json").read_text(encoding="utf-8"))

    def test_chest_suspended_stays(self):
        self.assertIn("ChestSuspended", (SRC / "IdleController.cs").read_text(encoding="utf-8"))
