"""Version 60 (Don, 24.11.2026): idle movement with MacGruber's IdlePoser on the AI character. While nobody moves or poses
her she shifts her weight from leg to leg; one toggle and one liveliness slider; the same stop / resume rules as the idle
poses (Body control, Dollmaster, the cooldown after a pose command or posing from outside) plus pose settle, scene load,
grab and a pose loaded from outside. The pure part (IdleMovement.cs) runs in a dotnet harness."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from aibody_companion import settings_file

from .test_plugin_menu import method_body, source
from . import test_version35 as v35

ROOT = Path(__file__).resolve().parents[2]
HARNESS = Path(__file__).parent / "csharp_idle_movement_harness" / "Program.cs"

# a standing pose in root space (hips ~1 m, feet on the floor); hands anchored to the chest
STANDING = [
    {"c": "hipControl", "py": 0.98}, {"c": "chestControl", "py": 1.32},
    {"c": "lFootControl", "px": -0.12, "py": 0.08}, {"c": "rFootControl", "px": 0.12, "py": 0.08},
    {"c": "lToeControl", "px": -0.13, "py": 0.02, "pz": 0.12}, {"c": "rToeControl", "px": 0.13, "py": 0.02, "pz": 0.12},
    {"c": "lHandControl", "px": -0.25, "py": -0.5}, {"c": "rHandControl", "px": 0.25, "py": -0.5},
]


def pose(**changes):
    parts = [dict(p) for p in STANDING]
    for p in parts:
        p.update(changes.get(p["c"], {}))
    return parts


@unittest.skipUnless(Path(v35.DOTNET).exists(), "dotnet SDK not installed")
class IdleMovementHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        shutil.copy(HARNESS, folder / "Program.cs")
        (folder / "Harness.csproj").write_text(f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework><OutputType>Exe</OutputType><Nullable>disable</Nullable>
  <EnableDefaultCompileItems>false</EnableDefaultCompileItems><NoWarn>CS0618</NoWarn>
  <DefineConstants>AIBODY_IDLEPOSER</DefineConstants></PropertyGroup>
  <ItemGroup><Compile Include="Program.cs" /><Compile Include="{ROOT / 'src/AIBody/IdleMovement.cs'}" /></ItemGroup>
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

    def call(self, **case):
        proc = subprocess.run([v35.DOTNET, str(self.exe)], input=json.dumps(case) + "\n", capture_output=True,
                              text=True, encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.splitlines()[0])

    def gate(self, *steps):
        return [s.split("|", 2) for s in self.call(cmd="gate", steps=list(steps))]

    # -- the plan -----------------------------------------------------------------------------------------------------

    def test_constants_package_label_and_liveliness_range(self):
        c = self.call(cmd="constants")
        self.assertEqual(c["label"], "AIBody Idle Movement")
        self.assertEqual(c["cslist"], "MacGruber.IdlePoser.9:/Custom/Scripts/MacGruber/IdlePoser/MacGruber_IdlePoser.cslist")
        self.assertEqual(c["suffix"], "_MacGruber.IdlePoser")
        self.assertEqual(c["default"], 0.5)
        self.assertNotIn("headControl@control", c["controls"], "the head belongs to AIBody's head motion and gaze")
        self.assertIn("lHandControl@chestControl", c["controls"])
        self.assertIn("hipControl@control", c["controls"])
        lv = {round(x["l"], 1): x for x in c["levels"]}
        self.assertAlmostEqual(lv[0.5]["amp"], 1.0, places=4, msg="the default = MacGruber's demo values")
        self.assertLess(lv[0.0]["amp"], lv[1.0]["amp"])
        self.assertGreater(lv[0.0]["wmin"], lv[1.0]["wmin"], "lively = shorter waits")
        self.assertTrue(all(x["wmin"] < x["wmax"] for x in c["levels"]))
        self.assertEqual(lv[-3.0], {**lv[0.0], "l": -3}, "clamped to 0")
        self.assertEqual(lv[7.0], {**lv[1.0], "l": 7}, "clamped to 1")

    def test_only_standing_poses_count_as_standing(self):
        self.assertTrue(self.call(cmd="standing", parts=STANDING))
        sitting = pose(hipControl={"py": 0.45})
        self.assertFalse(self.call(cmd="standing", parts=sitting))
        lying = pose(hipControl={"py": 0.2}, chestControl={"py": 0.22})
        self.assertFalse(self.call(cmd="standing", parts=lying))
        one_leg = pose(lFootControl={"py": 0.4})
        self.assertFalse(self.call(cmd="standing", parts=one_leg))
        self.assertFalse(self.call(cmd="standing", parts=[p for p in STANDING if p["c"] != "rFootControl"]))
        self.assertFalse(self.call(cmd="standing", parts=[]))

    def test_jump_detection_is_a_pose_from_outside_not_idleposers_motion(self):
        self.assertFalse(self.call(cmd="jump", m=0.01, dt=0.016))
        self.assertFalse(self.call(cmd="jump", m=0.055, dt=0.1))
        self.assertTrue(self.call(cmd="jump", m=0.3, dt=0.016))
        self.assertFalse(self.call(cmd="jump", m=0.3, dt=0.9), "a long frame is capped, not ignored")
        self.assertTrue(self.call(cmd="jump", m=0.5, dt=5.0))

    def test_weight_shift_signs_follow_the_demo(self):
        right = {p["c"]: p for p in self.call(cmd="shifted", parts=STANDING, side=1, a=1.0)}
        left = {p["c"]: p for p in self.call(cmd="shifted", parts=STANDING, side=-1, a=1.0)}
        base = {p["c"]: p for p in self.call(cmd="shifted", parts=STANDING, side=0, a=1.0)}
        self.assertEqual(base["hipControl"]["ry"], 0)
        self.assertAlmostEqual(left["hipControl"]["ry"], 20, places=3, msg="demo: right foot free -> hip +20")
        self.assertAlmostEqual(right["hipControl"]["ry"], -20, places=3)
        self.assertAlmostEqual(left["chestControl"]["ry"], 10, places=3)
        self.assertLess(left["hipControl"]["px"], 0, "hips over the standing (left) leg")
        self.assertGreater(right["hipControl"]["px"], 0)
        # the free foot lifts its heel and comes forward, the standing foot stays
        self.assertAlmostEqual(left["rFootControl"]["py"] - 0.08, 0.053, places=4)
        self.assertAlmostEqual(left["rFootControl"]["rx"], 31.4, places=3)
        self.assertEqual(left["lFootControl"], base["lFootControl"])
        self.assertAlmostEqual(right["lFootControl"]["py"] - 0.08, 0.053, places=4)
        self.assertEqual(right["rFootControl"], base["rFootControl"])
        self.assertEqual(left["lHandControl"], base["lHandControl"], "hands follow the chest, no own offset")
        calm = {p["c"]: p for p in self.call(cmd="shifted", parts=STANDING, side=-1, a=0.6)}
        self.assertAlmostEqual(calm["hipControl"]["ry"], 12, places=3)

    def test_state_set_is_valid_idleposer_json(self):
        text = self.call(cmd="build", uid="AI", parts=STANDING, l=0.5)
        data = json.loads(text)
        self.assertEqual(data["Info"], {"Format": "MacGruber.IdlePoser", "Version": "9", "Author": "AIBody"})
        self.assertEqual(data["InitialState"], "Neutral")
        self.assertEqual(data["Paused"], "false")
        self.assertEqual([c["Name"] for c in data["ControlCaptures"]], [p["c"] for p in STANDING])
        states = {s["Name"]: s for s in data["States"]}
        self.assertEqual(set(states), {"Neutral", "WeightLeft", "WeightRight", "Rest"})
        self.assertEqual(states["Neutral"]["StateType"], "2", "intermediate state between the shifts")
        self.assertEqual(states["Neutral"]["Transitions"], ["WeightLeft", "WeightRight", "Rest"])
        for name in ("WeightLeft", "WeightRight", "Rest"):
            s = states[name]
            self.assertEqual(s["StateType"], "0")
            self.assertEqual(s["Transitions"], ["Neutral"])
            self.assertEqual((s["WaitDurationMin"], s["WaitDurationMax"]), ("6", "14"))
            self.assertEqual(s["WaitForSync"], "false", "no LogicBricks / trigger needed")
        for s in data["States"]:
            self.assertEqual(set(s["ControlEntries"]), {p["c"] for p in STANDING})
            for control, e in s["ControlEntries"].items():
                self.assertEqual(e["AnchorMode"], "1")
                self.assertEqual(e["AnchorAAtom"], "AI", "anchored to the AI character itself")
                self.assertEqual(e["AnchorAControl"], "chestControl" if "Hand" in control else "control")
                for k in ("PX", "PY", "PZ", "RX", "RY", "RZ", "DampingTime"):
                    float(e[k])
        self.assertEqual(states["Neutral"]["ControlEntries"]["hipControl"]["PY"], "0.98", "Neutral = her own pose")
        self.assertEqual(states["WeightLeft"]["ControlEntries"]["hipControl"]["RY"], "20")
        self.assertIsNone(self.call(cmd="build", uid="AI", parts=[], l=0.5), "no hips: nothing to animate")
        odd = json.loads(self.call(cmd="build", uid='A"I\\x', parts=STANDING, l=1.0))
        self.assertEqual(odd["States"][0]["ControlEntries"]["hipControl"]["AnchorAAtom"], 'A"I\\x')

    # -- the gate: the same stop / resume rules as the idle poses -------------------------------------------------------

    def test_starts_when_idle_and_standing(self):
        steps = self.gate({}, {}, {})
        self.assertEqual([s[0] for s in steps], ["Start", "Keep", "Keep"])
        self.assertEqual(steps[0][1], "True")

    def test_stops_on_grab_or_outside_pose_and_waits_the_cooldown(self):
        steps = self.gate({}, {"outside": True}, {"cooldown": True}, {"cooldown": True}, {})
        self.assertEqual([s[0] for s in steps], ["Start", "Stop", "Keep", "Keep", "Start"])
        self.assertIn("from outside", steps[1][2])
        self.assertIn("cooldown", steps[2][2])

    def test_stops_while_a_pose_is_applied_scene_loads_body_control_off_or_dollmaster(self):
        for block, word in (({"settling": True}, "pose is applied"), ({"loading": True}, "scene loads"),
                            ({"body": False}, "Dollmaster"), ({"cooldown": True}, "pose command"),
                            ({"available": False}, "MacGruber.IdlePoser.9")):
            steps = self.gate({}, block, block, {})
            self.assertEqual([s[0] for s in steps], ["Start", "Stop", "Keep", "Start"], block)
            self.assertIn(word, steps[1][2], block)

    def test_toggle_off_and_on(self):
        steps = self.gate({}, {"enabled": False}, {}, {"enabled": True})
        self.assertEqual([s[0] for s in steps], ["Start", "Stop", "Keep", "Start"])
        self.assertEqual(steps[1][2], "off")
        self.assertEqual([s[0] for s in self.gate({"enabled": False}, {})], ["Keep", "Keep"], "off from the start")

    def test_not_standing_never_starts_but_a_running_shift_is_not_stopped_by_its_own_pose(self):
        self.assertEqual([s[0] for s in self.gate({"standing": False}, {"standing": False})], ["Keep", "Keep"])
        self.assertEqual([s[0] for s in self.gate({}, {"standing": False})], ["Start", "Keep"])

    def test_liveliness_change_rebuilds_once_and_stop_now_resets(self):
        steps = self.gate({}, {"lively": 0.9}, {}, {"lively": 0.9}, {"stopNow": "paused while a pose is applied"}, {})
        self.assertEqual([s[0] for s in steps], ["Start", "Rebuild", "Keep", "Keep", "StopNow", "Start"])
        self.assertEqual(steps[4][1], "False")


class PluginWiringTests(unittest.TestCase):
    def test_storables_have_defaults_and_reset_to_default(self):
        body = source("Body.cs")
        self.assertIn('IdleMovementLabel = "Idle movement"', body)
        self.assertIn('IdleMovementLivelinessLabel = "Idle movement liveliness"', body)
        self.assertIn('new JSONStorableBool("Idle movement", true,', body)
        self.assertIn('new JSONStorableFloat("Idle movement liveliness", IdleMovementPlan.DefaultLiveliness', body)
        self.assertIn("SettingsDefaults.Bool(_plugin, _idleMoveJson);", body)
        self.assertIn("SettingsDefaults.Float(_plugin, _idleMoveLivelyJson);", body)
        self.assertNotIn("JSONStorableStringChooser(IdleMovement", body, "no dropdown, so none can be empty")

    def test_ai_character_only_never_the_client(self):
        link = source("IdlePoserLink.cs")
        self.assertIn("AIBodyPlugin.ClientAtomName", link)
        body = source("Body.cs")
        self.assertIn("_poser = new IdlePoserLink(_atom);", body)

    def test_same_stop_resume_as_the_idle_poses(self):
        update = method_body(source("Body.cs"), "private void UpdateIdleMovement(float dt)")
        for part in ("BodyControl", "_idlePoses.NoteUserPose()", "_poser.Grabbed()", "_poser.Jumped(", "isLoading",
                     "CooldownLeft"):
            self.assertIn(part, update, part)
        before = source("Body.cs")
        self.assertIn('StopIdleMovement("paused while a pose is applied");', before)
        self.assertIn("public float CooldownLeft", source("IdlePoses.cs"))

    def test_one_writer_on_the_chest(self):
        body = source("Body.cs")
        self.assertIn("_idle.ChestSuspended = true;", method_body(body, "private string StartIdleMovement(List<IdlePart> basePose)"))
        self.assertIn("_idle.ChestSuspended = false;", method_body(body, "private void StopIdleMovement(string why)"))
        self.assertIn("&& !_chestSuspended) _lastChestOffset = ApplyOffset(_chest", source("IdleController.cs"))

    def test_idleposer_api_calls_are_the_evidenced_ones(self):
        link = source("IdlePoserLink.cs")
        for part in ('GetStorableByID("PluginManager") as MVRPluginManager', "CreatePlugin()", "pluginURLJSON.val",
                     'GetStringJSONParam("pluginLabel")', 'GetBoolJSONParam("enabled")', "LateRestoreFromJSON(",
                     '"idlepose"', ".isGrabbing", "FileManagerSecure.FileExists(", "TODO(verify)"):
            self.assertIn(part, link, part)
        self.assertNotIn("Animation Paused", link, "not registered by IdlePoser")
        # version 62: both files stay in the repository but are out of the .cslist (IdlePoser excluded at build time)
        self.assertNotIn("IdlePoserLink.cs", (ROOT / "src/AIBody/AIBody.cslist").read_text(encoding="utf-8"))
        self.assertNotIn("IdleMovement.cs", (ROOT / "src/AIBody/AIBody.cslist").read_text(encoding="utf-8"))

    def test_config_keys_and_ranges(self):
        result, _ = settings_file.validate({})
        self.assertIs(result["body"]["idle_movement"], True)
        self.assertEqual(result["body"]["idle_movement_liveliness"], 0.5)
        result, _ = settings_file.validate({"body": {"idle_movement": False, "idle_movement_liveliness": 7}})
        self.assertIs(result["body"]["idle_movement"], False)
        self.assertEqual(result["body"]["idle_movement_liveliness"], 1.0)
        example = json.loads((ROOT / "examples/config.json").read_text(encoding="utf-8"))
        self.assertIs(example["body"]["idle_movement"], True)
        body = source("Body.cs")
        self.assertIn('"idle_movement"', body)
        self.assertIn('"idle_movement_liveliness"', body)

    def test_meta_dependency_and_scene_untouched(self):
        meta = json.loads((ROOT / "packaging/meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["licenseType"], "FC")
        # version 62: no IdlePoser dependency while the IdlePoser code is excluded at build time
        self.assertNotIn("MacGruber.IdlePoser.9", meta["dependencies"])
        scene = (ROOT / "examples/scenes/AI-Buddy.json").read_text(encoding="utf-8")
        self.assertNotIn("IdlePoser", scene, "added at runtime by the plugin, not by the scene")
        self.assertNotIn("IdlePoser", (ROOT / "LICENSE").read_text(encoding="utf-8") if (ROOT / "LICENSE").exists() else "")

    def test_docs(self):
        protocol = (ROOT / "docs/TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("Idle movement", protocol)
        self.assertIn("MacGruber", (ROOT / "docs/CREDITS.md").read_text(encoding="utf-8"))
        audit = (ROOT / "docs/API_AUDIT.md").read_text(encoding="utf-8")
        for key in ("| E41 |", "| E42 |", "| E43 |", "| E44 |", "| E45 |"):
            self.assertIn(key, audit, key)


if __name__ == "__main__":
    unittest.main()
