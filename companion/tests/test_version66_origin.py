"""SOP-10 (Don 26.11.2026 20:55): the "origin" root reset - flat delta, sanity guard, sideways shift away from other people, log
line (pure C# OriginReset in RootReset.cs, run in a dotnet harness) and its wiring in PoseGuard / Body / AIBodyPlugin (source checks)."""
from __future__ import annotations

import json
import math
import re
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase

from . import test_version35 as v35
from .test_plugin_menu import method_body

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
HARNESS = Path(__file__).parent / "csharp_origin_harness" / "Program.cs"


@unittest.skipUnless(Path(v35.DOTNET).exists(), "dotnet SDK not installed")
class OriginMathTests(TestCase):
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
        result = subprocess.run([v35.DOTNET, "build", "-nologo", "-v", "q", "-o", str(folder / "out")], cwd=folder, capture_output=True,
                                text=True, timeout=240, env={**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1"})
        if result.returncode != 0:
            raise AssertionError("harness build failed:\n" + result.stdout + result.stderr)
        cls.exe = folder / "out" / "Harness.dll"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def ask(self, **case):
        proc = subprocess.run([v35.DOTNET, str(self.exe)], input=json.dumps(case) + "\n", capture_output=True, text=True,
                              encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_delta_is_origin_minus_current_and_flat(self):
        r = self.ask(cmd="delta", o=[1.0, 2.0], c=[1.5, 1.0], tol=0.02)
        self.assertEqual(r["v"], "Ok")
        self.assertAlmostEqual(r["dx"], -0.5, places=5)
        self.assertAlmostEqual(r["dz"], 1.0, places=5)

    def test_tiny_delta_is_left_alone(self):
        r = self.ask(cmd="delta", o=[0.0, 0.0], c=[0.01, 0.01], tol=0.02)
        self.assertEqual((r["v"], r["dx"], r["dz"]), ("Tiny", 0.0, 0.0))

    def test_absurd_delta_is_refused(self):
        for c in ([2390.0, 0.0], [15.0, 15.0], [0.0, -21.0]):
            r = self.ask(cmd="delta", o=[0.0, 0.0], c=c, tol=0.02)
            self.assertEqual((r["v"], r["dx"], r["dz"]), ("Absurd", 0.0, 0.0), c)
        self.assertEqual(self.ask(cmd="delta", o=[0.0, 0.0], c=[19.0, 0.0], tol=0.02)["v"], "Ok", "19 m is still believable")

    def test_nan_and_infinity_are_refused(self):
        # JSON has no NaN: the harness gets very large values that overflow to infinity in float
        r = self.ask(cmd="delta", o=[0.0, 0.0], c=[1e39, 0.0], tol=0.02)
        self.assertEqual(r["v"], "Absurd")
        self.assertFalse(self.ask(cmd="sane", p=[1e39, 0, 0], r=[0, 0, 0], max=20)["sane"])

    def test_sane_controller_position(self):
        self.assertTrue(self.ask(cmd="sane", p=[1, 1, 1], r=[0, 1, 0], max=20)["sane"])
        self.assertFalse(self.ask(cmd="sane", p=[2390, 0, 0], r=[0, 0, 0], max=20)["sane"])
        self.assertFalse(self.ask(cmd="sane", p=[0, 0, 0], r=[0, 0, 0], max=-1)["sane"])

    def test_no_neighbour_no_shift(self):
        r = self.ask(cmd="side", **{"from": [0, 0], "t": [1, 0], "others": [], "clear": 0.5})
        self.assertEqual((r["moved"], r["t"]), (False, [1.0, 0.0]))
        r = self.ask(cmd="side", **{"from": [0, 0], "t": [1, 0], "others": [3.0, 3.0], "clear": 0.5})
        self.assertFalse(r["moved"])

    def test_sideways_shift_is_perpendicular_minimal_and_clears_half_a_metre(self):
        # target (1, 0) reached from (0, 0) (moving along +x); the other person stands at (1, 0.2): inside 0.5 m
        r = self.ask(cmd="side", **{"from": [0, 0], "t": [1, 0], "others": [1.0, 0.2], "clear": 0.5})
        self.assertTrue(r["moved"])
        tx, tz = r["t"]
        self.assertAlmostEqual(tx, 1.0, places=4, msg="perpendicular to the way there: x unchanged")
        self.assertAlmostEqual(math.hypot(tx - 1.0, tz - 0.2), 0.5, places=3, msg="exactly 0.5 m: the smallest offset")
        self.assertLess(tz, 0.0, "away from the neighbour")

    def test_two_neighbours_are_both_cleared(self):
        r = self.ask(cmd="side", **{"from": [0, 0], "t": [1, 0], "others": [1.0, 0.2, 1.2, -0.3], "clear": 0.5})
        tx, tz = r["t"]
        for ox, oz in ((1.0, 0.2), (1.2, -0.3)):
            self.assertGreaterEqual(math.hypot(tx - ox, tz - oz), 0.5 - 1e-3)
        self.assertAlmostEqual(tx, 1.0, places=4)

    def test_no_movement_still_picks_a_direction(self):
        r = self.ask(cmd="side", **{"from": [1, 1], "t": [1, 1], "others": [1.1, 1.0], "clear": 0.5})
        self.assertTrue(r["moved"])
        self.assertGreaterEqual(math.hypot(r["t"][0] - 1.1, r["t"][1] - 1.0), 0.5 - 1e-3)

    def test_log_line_has_pose_delta_distance_and_collision_flag(self):
        line = self.ask(cmd="log", pose="Sit Down", dx=-0.5, dz=1.0, d=0.004, shift=True)["line"]
        for part in ("Sit Down", "-0.500 / 1.000", "0.004 m from the origin", "collision shift yes"):
            self.assertIn(part, line)
        self.assertIn("collision shift no", self.ask(cmd="log", pose="p", dx=0, dz=0, d=0, shift=False)["line"])


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def guard_text() -> str:
    pose = src("PoseController.cs")
    return pose[pose.index("public class PoseGuard"):pose.index("public static class BodyMover")]


class OriginWiringTests(TestCase):
    def test_named_constants(self):
        text = src("RootReset.cs")
        self.assertIn("public const float MaxDeltaMetres = 20f;", text)
        self.assertIn("public const float ClearanceMetres = 0.5f;", text)
        self.assertIn("public const float UnlockSeconds = 0.3f;", guard_text())

    def test_origin_is_captured_once_when_the_scene_has_loaded(self):
        plugin = src("AIBody.cs")
        take = method_body(plugin, "private void TakePlacement()")
        self.assertIn("_body.CaptureOrigin();", take)
        self.assertLess(take.index("_aiPlacement = PlacementSnapshot.Take(ai);"), take.index("_body.CaptureOrigin();"))
        self.assertIn("if (_placementTaken || !_settingsChecked", take, "after the scene restore (the config.json check), once")
        self.assertEqual(src("PoseController.cs").count("CaptureOrigin()"), 1, "only defined; called by Body")
        self.assertNotIn("CaptureOrigin", method_body(guard_text(), "public string Around(string what, Func<string> load, Atom partner)"),
                         "never at pose-apply time")

    def test_origin_follows_body_position_and_resets_with_reset_poses(self):
        body = src("Body.cs")
        self.assertIn("_poses.Guard.SetOriginForPlace(pos, rot);", method_body(body, "private void OnBodyMove()"))
        self.assertIn("_poses.Guard.SetOriginForPlace(_homePos, _homeRot);", method_body(body, "private void ResetBodyPosition()"))
        self.assertIn("_poses.Guard.ResetOrigin();", method_body(body, "public void ForgetBodyPosition()"))

    def test_one_move_after_the_pose_settled_physics_suspended_all_controllers(self):
        g = guard_text()
        update = method_body(g, "public void Update(float dt)")
        self.assertIn("if (UseOrigin && !_originDone)", update)
        self.assertLess(update.index("_age >= MinSeconds && _quiet >= QuietSeconds"), update.index("ApplyOrigin()"))
        apply = method_body(g, "private bool ApplyOrigin()")
        self.assertLess(apply.index("SuspendPhysics();"), apply.index("BodyMover.Shift(_atom, new Vector3(dx, 0f, dz));"))
        self.assertIn("new Vector3(dx, 0f, dz)", apply, "flat: the height stays the pose's")
        self.assertIn("_unlockIn = UnlockSeconds;", apply)
        self.assertIn("FreeControllerV3.PositionState.Lock", method_body(g, "private void SuspendPhysics()"))
        self.assertIn("_locked[i].currentPositionState = _lockedStates[i];", method_body(g, "private void ResumePhysics()"))
        shift = method_body(src("PoseController.cs"), "public static int Shift(Atom atom, Vector3 shift)")
        self.assertIn("atom.mainController.transform.rotation", shift, "no rotation change; every controller via Relocate")

    def test_absurd_delta_or_runaway_controller_skips_the_pose(self):
        g = guard_text()
        apply = method_body(g, "private bool ApplyOrigin()")
        self.assertIn("OriginReset.Verdict.Absurd", apply)
        self.assertIn("Reject(", apply)
        reject = method_body(g, "private void Reject(string reason)")
        for part in ("_snap.Restore();", "OnRejected(key)", "Log.Warn(", "bad list"):
            self.assertIn(part, reject)
        self.assertIn("string bad = Runaway();", method_body(g, "public void Hold()"), "a thrown body is caught at once")
        self.assertIn("string bad = Runaway();", apply, "and after the move")
        pose = src("PoseController.cs")
        self.assertIn("_badPoses.Add(key);", pose)
        self.assertIn("if (_badPoses.Contains(path))", method_body(pose, "public string LoadPose(string path)"))
        self.assertIn("Guard.PoseKey = path;", method_body(pose, "public string LoadPose(string path)"))

    def test_collision_avoidance_and_log(self):
        g = guard_text()
        apply = method_body(g, "private bool ApplyOrigin()")
        self.assertIn("OriginReset.Sideways(h.x, h.z, ref tx, ref tz, OthersFlat(), OriginReset.ClearanceMetres)", apply)
        self.assertIn("Log.Info(OriginReset.LogLine(_what, dx, dz, dist, shifted));", apply)
        others = method_body(g, "private float[] OthersFlat()")
        self.assertIn('a.type != "Person"', others)
        self.assertIn('"chestControl"', others)
        self.assertIn("RootReset.BodyControl", others)

    def test_montages_and_the_toggle_are_untouched(self):
        g = guard_text()
        self.assertIn("private bool UseOrigin { get { return _center && _hasOrigin; } }", g)
        self.assertIn("if (!UseOrigin) Center();", method_body(g, "public void Hold()"), "no origin yet: the v63 centring stays the fallback")

    def test_docs(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_V66.md").read_text(encoding="utf-8")
        for part in ("Root reset after a pose", "20 m", "0.5 m", "bad list"):
            self.assertIn(part, notes)
        self.assertIn("## T124 ", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
        self.assertIn("**Origin root reset**", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
