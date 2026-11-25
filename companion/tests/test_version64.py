"""Version 64 (25.11.2026, on top of v63): the idle movement with MacGruber's IdlePoser (v60-v63) is removed completely -
no files, no toggle, no code, no dependency - after v63 crashed VaM on plugin / scene load. Old config.json keys load and
are ignored. Everything else from v63 stays (root-position reset: test_version63.py). Version everywhere and English
release notes."""
from __future__ import annotations

import importlib.util
import json
import re
import zipfile
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__
from aibody_companion import settings_file
from aibody_companion import setup as first_start

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
WORDS = re.compile(r"IdlePoser|IdleMovement|idle_movement|_idleMove|_poser\b|ChestSuspended|AIBODY_IDLEPOSER")


class VersionTests(TestCase):
    def test_version_64_everywhere(self):
        self.assertEqual(__version__, "64")
        self.assertIn('PluginVersion = "64"', (SRC / "AIBody.cs").read_text(encoding="utf-8"))
        self.assertIn('version = "64"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 64)
        self.assertTrue(re.search(r"d0n\.AIBody\.64:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 64 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.63", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 64, package `d0n.AIBody.64.var`, release `v64`", readme)
        self.assertNotIn("**Idle movement**", readme)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 64, release; on top of v63)", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## T120", proto)
        self.assertIn("## T118 – Idle movement optional, off by default (version 63) – obsolete since version 64", proto)
        self.assertIn("removed in version 64", (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8"))
        switch = (ROOT / "docs" / "IDLEPOSER_BUILD_SWITCH.md").read_text(encoding="utf-8")
        self.assertIn("removed (version 64)", switch)

    def test_release_notes_english_without_personal_names(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v64**", notes)
        for part in ("d0n.AIBody.64.var", "AI-Buddy.jpg", "AI-Buddy.json", "Idle movement removed",
                     "Center body on control point", "T120"):
            self.assertIn(part, notes)
        self.assertIsNone(re.search(r"\b(" + "Le" + "on|Don)\b", notes), "no personal names in public release notes")


class IdleMovementRemovedTests(TestCase):
    def test_files_deleted_and_not_listed(self):
        for name in ("IdleMovement.cs", "IdlePoserLink.cs"):
            self.assertFalse((SRC / name).exists(), name)
        cslist = (SRC / "AIBody.cslist").read_text(encoding="utf-8").split()
        self.assertFalse([n for n in cslist if "Idle" in n and n not in ("IdleController.cs", "IdlePoses.cs")])
        self.assertIn("RootReset.cs", cslist, "the root-position reset of v63 stays")

    def test_no_reference_left_in_the_plugin_sources(self):
        for path in sorted(SRC.iterdir()):
            if path.is_file():
                hits = WORDS.findall(path.read_text(encoding="utf-8"))
                self.assertEqual(hits, [], path.name)

    def test_no_dependency(self):
        meta = json.loads((ROOT / "packaging" / "meta.json").read_text(encoding="utf-8"))
        self.assertNotIn("IdlePoser", json.dumps(meta))
        self.assertNotIn("IdlePoser", (ROOT / "examples" / "scenes" / "AI-Buddy.json").read_text(encoding="utf-8"))

    def test_old_config_keys_load_silently_and_are_ignored(self):
        for key in ("idle_movement", "idle_movement_opt_in", "idle_movement_liveliness"):
            self.assertNotIn(key, settings_file.DEFAULTS["body"])
            self.assertIn(("body", key), settings_file.LEGACY_KEYS)
        result, errors = settings_file.validate({"body": {"idle_movement": True, "idle_movement_opt_in": True,
                                                          "idle_movement_liveliness": 0.7, "pose_root_reset": False}})
        self.assertEqual(errors, [])
        self.assertNotIn("idle_movement", result["body"])
        self.assertIs(result["body"]["pose_root_reset"], False)
        example = json.loads((ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertFalse([k for k in example["body"] if k.startswith("idle_movement")])
        self.assertIs(example["body"]["pose_root_reset"], True)

    def test_pose_hook_and_update_have_no_idle_movement(self):
        body = (SRC / "Body.cs").read_text(encoding="utf-8")
        self.assertIn("_poses.BeforePoseLoad = () =>\n                {\n                    if (_idle != null) _idle.HoldForPose(PoseController.SettleSeconds);\n                };", body)
        self.assertNotIn('"Idle movement', body)

    def test_built_var_has_no_idleposer_code(self):
        spec = importlib.util.spec_from_file_location("build_var", ROOT / "tools" / "build_var.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        loose = ROOT / "dist" / build.LOOSE_SCENE
        kept = loose.read_bytes() if loose.exists() else None
        out = build.build(version_override=9064)
        self.addCleanup(out.unlink)
        self.addCleanup(lambda: loose.write_bytes(kept) if kept is not None else loose.unlink())
        with zipfile.ZipFile(out) as z:
            sources = [n for n in z.namelist() if n.startswith("Custom/Scripts/d0n/AIBody/")]
            self.assertTrue(any(n.endswith("RootReset.cs") for n in sources))
            for name in sources:
                if name.endswith((".cs", ".cslist")):
                    text = z.read(name).decode("utf-8-sig")
                    self.assertEqual(WORDS.findall(text), [], name)
            self.assertNotIn("IdlePoser", z.read("meta.json").decode("utf-8"))
