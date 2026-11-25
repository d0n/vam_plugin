"""Version 63 (25.11.2026, on top of v62): a root-position reset on pose load (toggle "Center body on control point": the
pose kept, the hips back over the control point; the pure math, RootReset.cs, runs in a dotnet harness). v63 also
compiled the idle movement back in as an optional toggle; version 64 removed it again (test_version64.py)."""
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
    def test_version_63_is_historical(self):
        """Historical: version 63 sources are gone after the v64 bump (and its idle movement toggle was removed in v64);
        consistency is test_version64. The root-position reset of v63 stays (tests below)."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version64.py").is_file())
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 63, release; on top of v62)", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## T118", proto)
        self.assertIn("## T119", proto)
        self.assertIn("`body.pose_root_reset`", (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8"))
        self.assertIn("**Center body on control point**", (ROOT / "README.md").read_text(encoding="utf-8"))


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
