"""Version 69 (28.11.2026, on top of v68; Don 00:44): a LARGE correction of her place (origin reset or a pose file's root move,
more than PhysicsFreeze.LargeMoveMetres flat) is made with her physics frozen (controllers locked + VaM simulation paused), then
SettleSeconds to settle; the small-steps fallback is code only (off, no menu). Also: Active always from config.json (Reload
Plugin), frame-stall warning, the sideways check sees other people's limbs and head, no expressions while muted. No enum."""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__
from aibody_companion import setup as first_start

from . import test_version35 as v35
from .test_plugin_menu import method_body
from .test_version68 import code, compiled_files

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
HARNESS = Path(__file__).parent / "csharp_freeze_harness" / "Program.cs"


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def guard_text() -> str:
    pose = src("PoseController.cs")
    return pose[pose.index("public class PoseGuard"):pose.index("public static class BodyMover")]


class VersionTests(TestCase):
    def test_version_69_everywhere(self):
        self.assertEqual(__version__, "69")
        self.assertIn('PluginVersion = "69"', src("AIBody.cs"))
        self.assertIn('version = "69"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 69)
        self.assertTrue(re.search(r"d0n\.AIBody\.69:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 69 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertIn("Status: version 69, package `d0n.AIBody.69.var`, release `v69`", (ROOT / "README.md").read_text(encoding="utf-8"))
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        for s in ("Release notes of version 69", "Physics freeze", "Active", "T127"):
            self.assertIn(s, notes)
        self.assertIn("## T127", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
        self.assertNotIn("## Reload Plugin: the Active toggle", (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8"))

    def test_still_no_enum_and_the_new_file_is_compiled(self):
        for f in compiled_files():
            self.assertIsNone(re.search(r"\benum\s+[A-Za-z_]", code(f.read_text(encoding="utf-8"))), f.name)


@unittest.skipUnless(Path(v35.DOTNET).exists(), "dotnet SDK not installed")
class FreezeMathTests(TestCase):
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

    def test_constants(self):
        c = self.ask(cmd="consts")
        self.assertAlmostEqual(c["large"], 0.3, places=5)
        self.assertAlmostEqual(c["settle"], 0.5, places=5)
        self.assertGreater(c["freeze"], 0)
        self.assertEqual(c["frames"], 5)
        self.assertFalse(c["steps"], "the small-steps fallback must stay off")
        self.assertAlmostEqual(c["stall"], 2.0)

    def test_threshold_is_flat_and_strictly_above_0_3_m(self):
        self.assertFalse(self.ask(cmd="large", dx=0.0, dz=0.0)["large"])
        self.assertFalse(self.ask(cmd="large", dx=0.3, dz=0.0)["large"])
        self.assertFalse(self.ask(cmd="large", dx=0.2, dz=0.2)["large"])      # 0.283 m
        self.assertTrue(self.ask(cmd="large", dx=0.22, dz=0.22)["large"])     # 0.311 m
        self.assertTrue(self.ask(cmd="large", dx=-2.0, dz=0.5)["large"])

    def test_steps_fallback_counts_and_stays_off(self):
        self.assertEqual(self.ask(cmd="steps", m=1.0, step=0.05)["n"], 20)
        self.assertEqual(self.ask(cmd="steps", m=0.31, step=0.05)["n"], 7)
        self.assertEqual(self.ask(cmd="steps", m=0.0, step=0.05)["n"], 1)
        self.assertEqual(self.ask(cmd="steps", m=1.0, step=0.0)["n"], 1)
        self.assertFalse(self.ask(cmd="usesteps", on=False, dx=2.0, dz=0.0)["use"])
        self.assertTrue(self.ask(cmd="usesteps", on=True, dx=2.0, dz=0.0)["use"])
        self.assertFalse(self.ask(cmd="usesteps", on=True, dx=0.1, dz=0.0)["use"])

    def test_freeze_log_line(self):
        line = self.ask(cmd="log", what="pose 'Sit'", dx=0.6, dz=-0.8, s=0.31)["line"]
        self.assertEqual(line, "Physics freeze: pose 'Sit' moved her 1.00 m (x 0.60 / z -0.80), physics frozen 0.31 s, then 0.5 s to settle")

    def test_frame_stall(self):
        self.assertFalse(self.ask(cmd="stall", s=2.0)["stall"])
        self.assertTrue(self.ask(cmd="stall", s=2.01)["stall"])
        line = self.ask(cmd="stalllog", s=6.4, pose="pose 'Doggie'", origin=True, freeze=False, d=1.25)["line"]
        self.assertEqual(line, "Frame stall: one VaM frame took 6.4 s; last pose 'pose 'Doggie'', origin reset running, physics freeze off, last delta 1.25 m")
        self.assertIn("last pose '-'", self.ask(cmd="stalllog", s=3, pose="", origin=False, freeze=False, d=0)["line"])

    def test_sideways_sees_limbs_and_head(self):
        c = self.ask(cmd="consts")["controls"]
        for cid in ("hipControl", "chestControl", "headControl", "lHandControl", "rHandControl", "lFootControl", "rFootControl",
                    "lKneeControl", "rKneeControl", "lElbowControl", "rElbowControl"):
            self.assertIn(cid, c)
        # only a hand of the other person reaches her place: she is still moved sideways, clear of the hand
        r = self.ask(cmd="side", **{"from": [0.0, -2.0], "t": [0.0, 0.0], "others": [0.1, 0.0]})
        self.assertTrue(r["moved"])
        self.assertGreaterEqual(math.hypot(r["t"][0] - 0.1, r["t"][1]), 0.5 - 1e-3)
        self.assertAlmostEqual(r["t"][1], 0.0, places=4)   # perpendicular to the way there


class FreezeWiringTests(TestCase):
    def test_apply_origin_freezes_large_moves_only(self):
        g = guard_text()
        apply = g[g.index("private bool ApplyOrigin()"):g.index("public string LastCenterNote")]
        self.assertIn("if (PhysicsFreeze.IsLarge(dx, dz))", apply)
        i = apply.index("if (PhysicsFreeze.IsLarge(dx, dz))")
        self.assertLess(apply.index("SuspendPhysics();"), i)
        block = apply[i:apply.index("BodyMover.Shift(_atom, new Vector3(dx, 0f, dz));")]
        self.assertIn("PauseSimulation();", block)
        self.assertIn("_freezing = true;", block)
        self.assertIn("PhysicsFreeze.UseSteps(PhysicsFreeze.StepsEnabled, dx, dz)", block)
        self.assertIn("_unlockIn = _freezing ? PhysicsFreeze.FreezeSeconds : UnlockSeconds;", apply)

    def test_pause_uses_the_evidenced_vam_call(self):
        g = guard_text()
        self.assertIn("SuperController.singleton.PauseSimulation(PhysicsFreeze.PauseFrames,", g)
        self.assertIn("E39", g[g.index("private static void PauseSimulation()") - 200:g.index("private static void PauseSimulation()")])

    def test_unfreeze_then_settle_and_one_info_line(self):
        g = guard_text()
        upd = g[g.index("public void Update(float dt)"):g.index("public void Rebase()")]
        self.assertLess(upd.index("if (_settleIn >= 0f)"), upd.index("if (_unlockIn >= 0f)"))
        self.assertIn("_settleIn = PhysicsFreeze.SettleSeconds;", upd)
        self.assertIn("Log.Info(PhysicsFreeze.LogLine(_what, _freezeDx, _freezeDz, _frozenFor));", upd)
        self.assertLess(upd.index("ResumePhysics();"), upd.index("_settleIn = PhysicsFreeze.SettleSeconds;"))

    def test_pose_root_moves_are_frozen_too(self):
        g = guard_text()
        hold = g[g.index("public void Hold()"):g.index("private void Center()")]
        self.assertIn("PhysicsFreeze.IsLarge(moved.x, moved.z)", hold)
        self.assertLess(hold.index("PauseSimulation();"), hold.index("BodyMover.Relocate(_atom, _pos, _rot);"))

    def test_new_pose_change_resets_the_freeze(self):
        begin = guard_text()
        begin = begin[begin.index("public void Begin(string what)"):begin.index("public void Hold()")]
        for s in ("_freezing = false;", "_settleIn = -1f;", "_stepsLeft = 0;"):
            self.assertIn(s, begin)

    def test_no_menu_entry_for_the_steps_fallback(self):
        for name in ("Body.cs", "AppLink.cs", "AIBody.cs"):
            self.assertNotIn("StepsEnabled", src(name))
        self.assertIn("public const bool StepsEnabled = false;", src("RootReset.cs"))

    def test_others_use_the_wider_list(self):
        g = guard_text()
        others = g[g.index("private float[] OthersFlat()"):g.index("private void Reject(")]
        self.assertIn("OriginReset.OtherControls", others)
        self.assertIn("c.transform.position", others)


class AdoptActiveTests(TestCase):
    def test_adopt_active_reads_connection_active(self):
        body = method_body(src("AppLink.cs"), "public void AdoptActive(JSONClass root)")
        self.assertIn('root["connection"] as JSONClass', body)
        self.assertIn('Protocol.Has(connection, "active")', body)
        self.assertIn('Protocol.GetBool(connection, "active", true)', body)
        self.assertIn("_activeJson.val = v", body)

    def test_called_on_every_load_next_to_the_token(self):
        upd = src("AIBody.cs")
        i = upd.index("_link.AdoptToken(file)")
        j = upd.index("_link.AdoptActive(file)")
        self.assertLess(i, j)
        self.assertLess(j, upd.index("if (file != null && !_settingsInitJson.val)"))
        self.assertIn('if (readOk) _diag.Run("Active from config.json", () => _link.AdoptActive(file));', upd)


class FrameStallWiringTests(TestCase):
    def test_update_measures_wall_clock_frames(self):
        a = src("AIBody.cs")
        upd = a[a.index("private void Update()"):a.index("if (_link != null) _link.UiVisible = visible;")]
        self.assertIn("DateTime.UtcNow", upd)
        self.assertIn("if (FrameStall.IsStall(frame)) Log.Warn(_body.FrameStallLine(frame));", upd)
        enable = a[a.index("private void OnEnable()"):a.index("private void OnDestroy()")]
        self.assertIn("_lastFrameUtc = DateTime.MinValue;", enable)

    def test_body_reports_pose_origin_freeze_and_delta(self):
        body = method_body(src("Body.cs"), "public string FrameStallLine(double seconds)")
        for s in ("g.What", "g.OriginRunning", "g.Freezing", "g.LastDelta"):
            self.assertIn(s, body)


class MuteExpressionTests(TestCase):
    def test_router_ignores_expressions_while_muted(self):
        r = src("CommandRouter.cs")
        case = r[r.index("case Protocol.CmdExpression:"):r.index("case Protocol.CmdSetMorphs:")]
        self.assertIn('if (IsMuted) { Log.Debug("Muted: expression ignored"); return null; }', case)
        self.assertLess(case.index("if (IsMuted)"), case.index("_expressions.SetExpression("))
        speak = r[r.index("case Protocol.CmdSpeak:"):r.index("case Protocol.CmdStopSpeaking:")]
        self.assertIn("&& !IsMuted)", speak)

    def test_mute_is_wired_from_the_menu_toggle(self):
        self.assertIn("_body.Muted = () => _link != null && _link.Muted;", src("AIBody.cs"))
        self.assertIn("_router.Muted = () => Muted != null && Muted();", src("Body.cs"))
