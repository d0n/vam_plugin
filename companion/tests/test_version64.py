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
    def test_version_64_is_historical(self):
        """Historical: version 64 sources are gone after the v65 bump; consistency is test_version65."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version65.py").is_file())
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 64, release; on top of v63)", spec)
        self.assertIn("## T120", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))


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
