"""Version 63 (25.11.2026, on top of v62): MacGruber IdlePoser idle movement compiled in again as an optional toggle that
is off by default (nothing of IdlePoser runs while it is off, no package dependency), and a root-position reset on pose
load (toggle "Center body on control point": the pose kept, the hips back over the control point). The pure math
(RootReset.cs) runs in a dotnet harness. Version everywhere and English release notes."""
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

from aibody_companion import __version__
from aibody_companion import settings_file
from aibody_companion import setup as first_start

from .test_plugin_menu import method_body
from . import test_version35 as v35

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
HARNESS = Path(__file__).parent / "csharp_root_reset_harness" / "Program.cs"


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class VersionTests(TestCase):
    def test_version_63_everywhere(self):
        self.assertEqual(__version__, "63")
        self.assertIn('PluginVersion = "63"', src("AIBody.cs"))
        self.assertIn('version = "63"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 63)
        self.assertTrue(re.search(r"d0n\.AIBody\.63:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 63 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.62", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 63, package `d0n.AIBody.63.var`, release `v63`", readme)
        self.assertIn("**Center body on control point**", readme)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 63, release; on top of v62)", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## T118", proto)
        self.assertIn("## T119", proto)
        config = (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8")
        for key in ("`body.pose_root_reset`", "`body.idle_movement_opt_in`"):
            self.assertIn(key, config)
        switch = (ROOT / "docs" / "IDLEPOSER_BUILD_SWITCH.md").read_text(encoding="utf-8")
        for part in ("off by default", "MacGruber.IdlePoser.9", "IdleMovementOn", "CreateIdleMovement", "idle_movement_opt_in"):
            self.assertIn(part, switch)

    def test_release_notes_english_without_personal_names(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v63**", notes)
        for part in ("d0n.AIBody.63.var", "AI-Buddy.jpg", "AI-Buddy.json", "optional toggle, off by default",
                     "Root-position reset on pose load", "Center body on control point", "T118", "T119", "Known risk"):
            self.assertIn(part, notes)
        self.assertIsNone(re.search(r"\b(" + "Le" + "on|Don)\b", notes), "no personal names in public release notes")


class IdleMovementOptionalTests(TestCase):
    def test_compiled_in_again(self):
        cslist = src("AIBody.cslist").split()
        for name in ("IdleMovement.cs", "IdlePoserLink.cs", "RootReset.cs"):
            self.assertIn(name, cslist)
        self.assertLess(cslist.index("RootReset.cs"), cslist.index("PoseController.cs"))
        for path in sorted(SRC.glob("*.cs")):
            self.assertNotIn("AIBODY_IDLEPOSER", path.read_text(encoding="utf-8"), path.name)

    def test_off_by_default_everywhere(self):
        body = src("Body.cs")
        self.assertIn("public const bool IdleMovementDefault = false;", body)
        self.assertIn('new JSONStorableBool("Idle movement", IdleMovementDefault,', body)
        self.assertIn("SettingsDefaults.Bool(_plugin, _idleMoveJson);", body, "Reset to Default -> off")
        self.assertIs(settings_file.DEFAULTS["body"]["idle_movement"], False)
        self.assertIs(settings_file.DEFAULTS["body"]["idle_movement_opt_in"], True)
        result, errors = settings_file.validate({})
        self.assertIs(result["body"]["idle_movement"], False)
        example = json.loads((ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertIs(example["body"]["idle_movement"], False)
        self.assertIs(example["body"]["idle_movement_opt_in"], True)

    def test_old_config_without_opt_in_stays_off(self):
        body = src("Body.cs")
        rule = method_body(body, "public static bool IdleMovementFromConfig(bool optIn, bool hasKey, bool value)")
        self.assertIn("return optIn && hasKey && value;", rule)
        self.assertIn('IdleMovementFromConfig(Protocol.GetBool(body, "idle_movement_opt_in", false),', body)
        self.assertIn('Protocol.Has(body, "idle_movement"), Protocol.GetBool(body, "idle_movement", IdleMovementDefault));', body)
        self.assertIn('body["idle_movement_opt_in"].AsBool = true;', body)

    def test_nothing_of_idleposer_runs_while_off(self):
        body = src("Body.cs")
        self.assertIn("public bool IdleMovementOn { get { return _idleMoveJson != null && _idleMoveJson.val; } }", body)
        update = method_body(body, "public void Update(float dt)")
        calls = [ln.strip() for ln in update.splitlines() if "UpdateIdleMovement(dt)" in ln]
        self.assertEqual(len(calls), 2, calls)
        for ln in calls:
            self.assertTrue(ln.startswith("if (IdleMovementOn) UpdateIdleMovement(dt);"), ln)
        # created only on first use (no IdlePoserLink / gate in Init)
        self.assertEqual(body.count("new IdlePoserLink(_atom)"), 1)
        self.assertEqual(body.count("new IdleMovementGate()"), 1)
        create = method_body(body, "private void CreateIdleMovement()")
        self.assertIn("_poser = new IdlePoserLink(_atom);", create)
        self.assertIn("CreateIdleMovement();", method_body(body, "private void UpdateIdleMovement(float dt)"))
        self.assertNotIn('_diag.Run("Idle movement (IdlePoser)"', body)
        # every StopIdleMovement call outside the idle movement itself is guarded
        for line in body.splitlines():
            if "StopIdleMovement(\"" in line and "private" not in line:
                self.assertIn("_idleMove != null || _poser != null", line, line.strip())
        self.assertIn("IdleMovementOn || _idleMove != null ? IdleMovementInfo() : IdleMovementOffInfo", body)

    def test_toggle_in_menu_and_config(self):
        body = src("Body.cs")
        self.assertIn("page.Toggle(_idleMoveJson);", body)
        self.assertIn('body["idle_movement"].AsBool = _idleMoveJson.val;', body)

    def test_no_hard_dependency(self):
        meta = json.loads((ROOT / "packaging" / "meta.json").read_text(encoding="utf-8"))
        self.assertFalse([n for n in meta.get("dependencies", {}) if "IdlePoser" in n])
        link = src("IdlePoserLink.cs")
        self.assertIn("FileManagerSecure.FileExists(IdleMovementPlan.PoserCslist)", link)
        self.assertIn("AIBody does not depend on it", link)


class RootResetWiringTests(TestCase):
    def test_setting_default_on_menu_and_config(self):
        body = src("Body.cs")
        self.assertIn('new JSONStorableBool("Center body on control point", RootReset.DefaultOn,', body)
        self.assertIn("SettingsDefaults.Bool(_plugin, _rootResetJson);", body)
        self.assertIn("page.Toggle(_rootResetJson);", body)
        self.assertIn('body["pose_root_reset"].AsBool = _rootResetJson.val;', body)
        self.assertIn('_rootResetJson.val = Protocol.GetBool(body, "pose_root_reset", _rootResetJson.val);', body)
        self.assertIn("_poses.Guard.CenterBody = _rootResetJson == null || _rootResetJson.val;", body)
        self.assertIs(settings_file.DEFAULTS["body"]["pose_root_reset"], True)
        result, _ = settings_file.validate({"body": {"pose_root_reset": False}})
        self.assertIs(result["body"]["pose_root_reset"], False)

    def test_guard_centers_during_every_pose_change_but_montages(self):
        pc = src("PoseController.cs")
        hold = method_body(pc, "public void Hold()")
        self.assertLess(hold.index("Center();"), hold.index("BodyMover.Relocate(_atom, _pos, _rot);"))
        begin = method_body(pc, "public void Begin(string what)")
        self.assertIn("_center = RootReset.Applies(CenterBody, false);", begin)
        around = method_body(pc, "public string Around(string what, Func<string> load, Atom partner)")
        self.assertIn("if (partner != null || what == MontageWhat) _center = RootReset.Applies(CenterBody, true);", around)
        self.assertIn('public const string MontageWhat = "Dollmaster montage";', pc)
        self.assertIn('guard.Around("Dollmaster montage", load,', src("DmMontageController.cs"))

    def test_center_moves_everything_but_the_control_point(self):
        pc = src("PoseController.cs")
        center = method_body(pc, "public static float CenterOnControl(Atom atom, float tolerance)")
        for part in ("GetStorableByID(RootReset.BodyControl) as FreeControllerV3", "Quaternion.Inverse(root.rotation)",
                     "RootReset.LocalShift(", "if (c == null || c == main) continue;", "c.transform.position = pos[i] + shift;"):
            self.assertIn(part, center, part)
        self.assertNotIn("main.transform.position =", center, "the control point never moves")
        self.assertNotIn(".rotation =", center, "rotations (the pose) are kept")

    def test_idle_movement_start_recenters_before_capture(self):
        update = method_body(src("Body.cs"), "private void UpdateIdleMovement(float dt)")
        self.assertIn("if (_poses != null && _poses.Guard.CenterNow() > 0f) pose = null;", update)
        self.assertLess(update.index("CenterNow()"), update.index("StartIdleMovement(pose ?? _poser.CaptureBase())"))


@unittest.skipUnless(Path(v35.DOTNET).exists(), "dotnet SDK not installed")
class RootResetHarnessTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        shutil.copy(HARNESS, folder / "Program.cs")
        (folder / "Harness.csproj").write_text(f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework><OutputType>Exe</OutputType><Nullable>disable</Nullable>
  <EnableDefaultCompileItems>false</EnableDefaultCompileItems></PropertyGroup>
  <ItemGroup><Compile Include="Program.cs" /><Compile Include="{SRC / 'RootReset.cs'}" /></ItemGroup>
</Project>""", encoding="utf-8")
        result = subprocess.run([v35.DOTNET, "build", "-nologo", "-v", "q", "-o", str(folder / "out")], cwd=folder,
                                capture_output=True, text=True, timeout=240,
                                env={**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1"})
        if result.returncode != 0:
            raise AssertionError("harness build failed:\n" + result.stdout + result.stderr)
        cls.exe = folder / "out" / "Harness.dll"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_cases(self, *cases):
        proc = subprocess.run([v35.DOTNET, str(self.exe)], input="".join(json.dumps(c) + "\n" for c in cases),
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return [json.loads(ln) for ln in proc.stdout.splitlines()]

    def shift(self, x, y, z, tol=0.02):
        return self.run_cases({"cmd": "shift", "x": x, "y": y, "z": z, "tol": tol})[0]

    def test_constants(self):
        c = self.run_cases({"cmd": "constants"})[0]
        self.assertEqual(c, {"body": "hipControl", "tol": 0.02, "on": True})

    def test_flat_offset_is_taken_back_height_kept(self):
        r = self.shift(0.4, 0.95, -0.3)
        self.assertAlmostEqual(r["moved"], 0.5, places=5)
        self.assertAlmostEqual(r["sx"], -0.4, places=6)
        self.assertEqual(r["sy"], 0.0, "the height of the pose stays (sitting, lying)")
        self.assertAlmostEqual(r["sz"], 0.3, places=6)

    def test_hips_over_control_point_after_the_shift(self):
        for x, y, z in ((1.7, 0.4, 2.2), (-0.05, 1.0, 0.0), (0.0, 0.2, -3.0)):
            r = self.shift(x, y, z)
            self.assertAlmostEqual(x + r["sx"], 0.0, places=5)
            self.assertAlmostEqual(z + r["sz"], 0.0, places=5)
            self.assertAlmostEqual(y + r["sy"], y, places=6)

    def test_within_tolerance_nothing_moves(self):
        for x, z in ((0.0, 0.0), (0.01, 0.01), (0.0, 0.02), (-0.014, 0.014)):
            self.assertEqual(self.shift(x, 1.0, z), {"moved": 0.0, "sx": 0.0, "sy": 0.0, "sz": 0.0}, (x, z))
        self.assertGreater(self.shift(0.0, 1.0, 0.021)["moved"], 0.0)
        self.assertEqual(self.shift(0.0, 1.0, 0.5, tol=1.0)["moved"], 0.0)
        self.assertGreater(self.shift(0.0, 1.0, 0.001, tol=-1.0)["moved"], 0.0, "a negative tolerance counts as 0")

    def test_vertical_offset_alone_never_moves(self):
        self.assertEqual(self.shift(0.0, 5.0, 0.0)["moved"], 0.0)
        self.assertEqual(self.shift(0.0, -1.0, 0.0)["moved"], 0.0)

    def test_applies_only_when_on_and_not_a_montage(self):
        rows = self.run_cases(*({"cmd": "applies", "enabled": e, "montage": m} for e in (True, False) for m in (False, True)))
        self.assertEqual([r["applies"] for r in rows], [True, False, False, False])
