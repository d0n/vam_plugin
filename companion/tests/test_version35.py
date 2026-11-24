"""Version 35 (Leon, 20.11.2026): idle poses, own idle motion / breathing, voice pose commands with speech-to-text
punctuation, Persona menu, no start note in the menu, 'Test tone via companion', Body control, first-start questions."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from aibody_companion import __version__, cli, pose_commands, settings_file
from aibody_companion import setup as first_start

from .fakes import FakeClock, FakeHttp, FakePlugin
from .test_e2e_simulation import Sim
from .test_plugin_menu import method_body, source

ROOT = Path(__file__).resolve().parents[2]
DOTNET = shutil.which("dotnet") or str(Path.home() / ".dotnet" / "dotnet")
STARTERS = list(pose_commands.STARTER_COMMANDS)


# -- 1. starter poses from the start ------------------------------------------------------------------------------

class StarterPoseTests(unittest.TestCase):
    def test_missing_empty_or_unusable_list_gives_the_starters_on_both_sides(self):
        load = method_body(source("Body.cs"), "public void LoadPoseCommands(JSONClass root)")
        self.assertIn("if (v.Count == 0)", load)
        self.assertIn("v.SetStarters();", load)
        for data in ({}, {"poses": {"commands": []}}, {"poses": {"commands": [{"command": "", "pose": "x"}]}}):
            result, _ = settings_file.validate(data)
            self.assertEqual([e["command"] for e in result["poses"]["commands"]], STARTERS, data)
        example = json.loads((ROOT / "examples/config.json").read_text(encoding="utf-8"))
        self.assertEqual([e["command"] for e in example["poses"]["commands"]], STARTERS)


# -- 2. idle poses: the plugin's real IdlePoses.cs, outside VaM ------------------------------------------------------

@unittest.skipUnless(Path(DOTNET).exists(), "dotnet SDK not installed")
class IdlePoseSchedulerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        shutil.copy(Path(__file__).parent / "csharp_idle_harness" / "Program.cs", folder / "Program.cs")
        (folder / "Harness.csproj").write_text(f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework><OutputType>Exe</OutputType>
  <EnableDefaultCompileItems>false</EnableDefaultCompileItems><NoWarn>CS0618</NoWarn></PropertyGroup>
  <ItemGroup><Compile Include="Program.cs" /><Compile Include="{ROOT / 'src/AIBody/PoseVocabulary.cs'}" />
  <Compile Include="{ROOT / 'src/AIBody/IdlePoses.cs'}" /></ItemGroup>
</Project>""", encoding="utf-8")
        result = subprocess.run([DOTNET, "build", "-nologo", "-v", "q", "-o", str(folder / "out")], cwd=folder,
                                capture_output=True, text=True, timeout=240,
                                env={**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1"})
        if result.returncode != 0:
            raise AssertionError("harness build failed:\n" + result.stdout + result.stderr)
        cls.exe = folder / "out" / "Harness.dll"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_case(self, steps, poses=("Stand Up", "Sit Down", "Lay Down", "Turn Around"), commands=None,
                 default="Stand Up", lo=20, hi=40, enabled=True, fail=()):
        case = {"poses": list(poses), "commands": commands, "default": default, "min": lo, "max": hi,
                "enabled": enabled, "steps": steps, "fail": list(fail)}
        proc = subprocess.run([DOTNET, str(self.exe)], input=json.dumps(case) + "\n", capture_output=True, text=True,
                              encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return [tuple(x.split(":", 1)) for x in json.loads(proc.stdout.splitlines()[0])]

    def test_quiet_time_changes_to_random_poses_never_twice_in_a_row(self):
        # version 51: random of ALL poses (the default pose is one of them), no forced return to the default pose;
        # the wait is clamped to the 30 s minimum (20 -> 30)
        chosen = self.run_case([[1.0, False, True, "", 600]])
        names = [n for _, n in chosen]
        self.assertGreaterEqual(len(names), 10)
        self.assertTrue(all(a != b for a, b in zip(names, names[1:])), names)
        self.assertEqual(set(names), {"Stand Up", "Sit Down", "Lay Down", "Turn Around"})
        steps = [int(i) for i, _ in chosen]
        gaps = [b - a for a, b in zip([-1] + steps, steps)]
        self.assertTrue(all(30 <= g <= 41 for g in gaps), gaps)

    def test_only_poses_the_character_has(self):
        # version 51: every pose the character has is in the pool (Dance too, though no pose command links it);
        # the pose commands without a pose file (Sit Down, ...) are not
        names = [n for _, n in self.run_case([[1.0, False, True, "", 600]], poses=("Stand Up", "Prone", "Dance"))]
        self.assertEqual(set(names), {"Prone", "Stand Up", "Dance"})
        self.assertEqual(self.run_case([[1.0, False, True, "", 600]], poses=()), [], "nothing available")
        own = [n for _, n in self.run_case([[1.0, False, True, "", 300]], poses=("sitting", "Stand Up"),
                                           commands=[["Have a seat", "sitting"]])]
        self.assertIn("sitting", own)

    def test_never_while_someone_speaks_and_not_with_body_control_off_or_toggle_off(self):
        self.assertEqual(self.run_case([[1.0, True, True, "", 600]]), [], "speaking / listening all the time")
        self.assertEqual(self.run_case([[1.0, False, False, "", 600]]), [], "Body control off")
        self.assertEqual(self.run_case([[1.0, False, True, "", 600]], enabled=False), [], "toggle off")
        # speech every 15 s resets the quiet time: a 20-40 s wait is never reached
        steps = [[1.0, False, True, "", 14], [1.0, True, True, "", 1]] * 40
        self.assertEqual(self.run_case(steps), [])

    def test_a_user_pose_command_is_respected_for_the_cooldown(self):
        chosen = self.run_case([[1.0, False, True, "user", 1], [1.0, False, True, "", 300]])
        self.assertTrue(chosen)
        self.assertGreaterEqual(int(chosen[0][0]), 119, "120 s cooldown after the user's pose command")

    def test_without_the_default_pose_it_still_changes_but_never_goes_back(self):
        names = [n for _, n in self.run_case([[1.0, False, True, "", 600]], default="Nope")]
        self.assertTrue(names)
        self.assertNotIn("Nope", names)


    # version 57 (Leon 15:57): a failing pose is dropped at once and the next one comes on the next frame
    def test_failed_pose_dropped_and_next_right_away(self):
        chosen = self.run_case([[1.0, False, True, "", 1200]], fail=("Sit Down",))
        names = [n for _, n in chosen]
        self.assertIn("Sit Down!", names)
        k = names.index("Sit Down!")
        self.assertEqual(int(chosen[k + 1][0]), int(chosen[k][0]) + 1, "the next pose on the very next step, no wait")
        self.assertNotIn("Sit Down", names[k + 1:], "never again this session")
        self.assertEqual(names.count("Sit Down!"), 1)
        self.assertGreater(len([n for n in names[k + 1:] if not n.endswith("!")]), 2, "idle poses go on")

    def test_all_failing_ends_once_without_a_loop(self):
        chosen = self.run_case([[1.0, False, True, "", 600]], fail=("Stand Up", "Sit Down", "Lay Down", "Turn Around"))
        names = [n for _, n in chosen]
        self.assertEqual(sorted(n for n in names if n.endswith("!")),
                         ["Lay Down!", "Sit Down!", "Stand Up!", "Turn Around!"], "each fails once")
        self.assertEqual(names[-1], "EMPTY")
        self.assertEqual(names.count("EMPTY"), 1, "logged once")
        steps = [int(i) for i, _ in chosen]
        self.assertEqual(steps[1:], [steps[0] + n for n in range(1, len(steps))], "one after the other, no cooldown")


class IdlePosePluginTests(unittest.TestCase):
    def test_body_wires_the_scheduler_ui_settings_and_cooldown(self):
        body = source("Body.cs")
        for part in ('new JSONStorableBool("Idle poses", true', '"Idle pose min wait (s)"', '"Idle pose max wait (s)"',
                     '"Idle default pose"', "page.Toggle(_idlePosesJson);", "page.ScrollablePopup(_idlePoseDefaultJson);",
                     'body["idle_poses"]', 'body["idle_pose_min_s"]', 'body["idle_pose_max_s"]', 'body["idle_pose_default"]',
                     "_idlePoses.Update(dt, busy, BodyControl, _poses.Vocabulary, _poses.IdlePoolNames(IdleAllFiles), _poses.PoseNames)", "_idlePoses.NoteUserPose();",
                     "_poses.OnPoseLoaded = () => { if (_idle != null) _idle.Rebase(); };"):
            self.assertIn(part, body, part)
        self.assertIn("IdlePoses.cs", source("AIBody.cslist"))
        self.assertEqual(settings_file.RANGES[("body", "idle_pose_min_s")], (30.0, 18000.0))   # version 51
        self.assertEqual(settings_file.DEFAULTS["body"]["idle_pose_default"], "Stand Up")
        self.assertIs(settings_file.DEFAULTS["body"]["idle_poses"], True)

    def test_scheduler_is_pure_and_sandbox_safe(self):
        text = source("IdlePoses.cs")
        self.assertNotIn("using UnityEngine", text)
        self.assertNotIn("this[", text)


# -- 3. own idle motion and breathing -----------------------------------------------------------------------------

class OwnIdleMotionTests(unittest.TestCase):
    def test_breath_cycle_runs_without_the_morph_and_moves_chest_and_head(self):
        update = method_body(source("BreathingController.cs"), "public void Update(float deltaTime, bool speaking)")
        self.assertLess(update.index("_phase +="), update.index("if (_morph == null)"))
        idle = source("IdleController.cs")
        for part in ('GetStorableByID("chestControl")', "TODO(verify)", "chestPitch = -breathCycle * breathDepth",
                     "_shiftTarget", "public void Rebase()"):
            self.assertIn(part, idle, part)

    def test_no_third_party_plugin_code_or_dependency(self):
        for name in ("IdleController.cs", "BreathingController.cs", "IdlePoses.cs"):
            text = source(name)
            for word in ("MacGruber", "IdleMover", "Idle Mover"):
                self.assertNotIn(word, text, f"{name}: {word}")
        meta = json.loads((ROOT / "packaging/meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta.get("licenseType"), "FC")
        # Idle motion / breathing still adds no plugin package of its own (no MacGruber / Idle Mover).
        # meta.json "dependencies" now lists third-party content used by the AI-Buddy example scene, not the plugin.
        self.assertNotIn("MacGruber", json.dumps(meta.get("dependencies", {})))
        self.assertNotIn("IdleMover", json.dumps(meta.get("dependencies", {})))


# -- 4. voice pose commands ---------------------------------------------------------------------------------------

class VoicePoseCommandTests(unittest.TestCase):
    def test_speech_to_text_endings_match_exactly_and_the_gate_stays_strict(self):
        v = pose_commands.PoseVocabulary(pose_commands.starter_entries())
        for text in ("Sit down.", "sit down,", "Sit down;", "Sit down:", "Turn around!", "turn around, ", "Lay down\uff0c",
                     "BEND OVER...", "Stand up?"):
            self.assertIsNotNone(v.match(text), repr(text))
        for text in ("Sit down, please", "Okay, sit down", "Setz dich hin", "Dreh dich um", ",Sit down", "Sit, down"):
            self.assertIsNone(v.match(text), repr(text))

    def test_the_plugin_uses_the_same_trailing_set(self):
        text = source("PoseVocabulary.cs")
        for ch in ("','", "';'", "':'", "'\\uff0c'", "'\\uff1b'", "'\\uff1a'", "'\\u3001'"):
            self.assertIn(ch, method_body(text, "private static bool IsTrailing(char c)"), ch)


# -- 5. Persona menu ----------------------------------------------------------------------------------------------

class PersonaMenuTests(unittest.TestCase):
    def test_menu_always_has_none_and_refills_on_open(self):
        link = source("AppLink.cs")
        self.assertIn("_personaJson.popupOpenCallback = RefreshPersonaChoices;", link)
        refresh = method_body(link, "private void RefreshPersonaChoices()")
        self.assertIn("new List<string>(StarterPersonas)", refresh)   # version 50: Anna + Marc, no "(none)"
        self.assertIn("page.Popup(_personaJson);", method_body(link, "public void BuildAiSection(UiPage page)"))
        self.assertIn("RefreshPersonaChoices();", method_body(link, "private void SetPersonaChoices(JSONArray names)"))


# -- 7. Test tone via companion -----------------------------------------------------------------------------------

class TestToneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_companion_answers_with_a_speak_and_reports_it(self):
        sim = Sim(self.tmp.name, self.clock, FakeHttp())
        sim.start_app()
        plugin = FakePlugin(Path(self.tmp.name), self.clock, mode="chain")
        plugin.start()
        sim.run(plugin, 3)
        plugin.request_test_tone()
        sim.run(plugin, 2)
        speak = sim.sent(plugin, "speak")[-1]
        self.assertEqual((speak["text"], speak["queue"]), ("Test tone", "interrupt"))
        self.assertTrue((Path(self.tmp.name) / speak["audio"]).is_file())
        self.assertIn(("started", speak["id"]), plugin.speech_events)
        self.assertTrue(plugin.turn.startswith("Test tone sent"), plugin.turn)

    def test_the_plugin_waits_for_the_app_and_shows_the_result_on_top(self):
        link = source("AppLink.cs")
        request = method_body(link, "public void RequestTestTone()")
        self.assertIn("_testTonePending = true;", request)
        self.assertIn("SendTestTone();", request)
        tick = method_body(link, "private void TickTestTone(float dt)")
        self.assertIn("if (_appAlive) SendTestTone();", tick)
        self.assertIn('Protocol.GetString(msg, "text", "") != "Test tone"', method_body(link, "private void NoteTestToneSpeak(JSONClass msg)"))
        self.assertIn("NoteTestToneSpeak(msg);", method_body(link, "private void Handle(JSONClass msg)"))
        self.assertIn("_link.TestToneStatus", source("AIBody.cs"))


# -- 8. Body control ----------------------------------------------------------------------------------------------

class BodyControlTests(unittest.TestCase):
    def test_body_control_gates_every_body_command_and_the_idle_poses(self):
        router = method_body(source("CommandRouter.cs"), "private static bool IsBodyCommand(string type)")
        for cmd in ("CmdExpression", "CmdSetMorphs", "CmdResetMorphs", "CmdGesture", "CmdPose", "CmdTrigger",
                    "CmdIdle", "CmdBreathing"):
            self.assertIn(cmd, router)
        body = source("Body.cs")
        self.assertIn("BodyControlHelp", method_body(body, "public string CharacterInfoText()"))
        self.assertIn("no idle poses", body)


# -- first-start questions ----------------------------------------------------------------------------------------

# The version 35 setup questions were replaced in version 36: see tests/test_version36.py (WizardTests).


if __name__ == "__main__":
    unittest.main()
