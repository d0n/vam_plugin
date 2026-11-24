"""Version 58 (Don, voice 24.11.2026 16:07-16:09, explicit go): pose commands inside a sentence (pose_commands.find,
German phrases for the built-in commands, negations ignored), a substitute pose for built-in commands without their
pose file, and no empty dropdown after Reset to Default (Pose command, gender, Dollmaster Thrust Control)."""
from __future__ import annotations

import unittest
from pathlib import Path

from aibody_companion import pose_commands
from aibody_companion.pose_commands import PoseVocabulary

from .test_plugin_menu import method_body
from . import test_pose_commands as tpc
from .test_pose_commands import NEAR_MISSES

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class SentenceMatchTests(unittest.TestCase):
    def setUp(self):
        self.v = PoseVocabulary(pose_commands.starter_entries())

    def found(self, text):
        entry, _ = self.v.find(text)
        return entry["command"] if entry else None

    def test_command_inside_a_sentence(self):
        for text, want in (("please sit down now", "Sit Down"), ("Sit Down", "Sit Down"), ("sit down, please!", "Sit Down"),
                           ("Hey, could you stand up?", "Stand Up"), ("SIT-DOWN", "Sit Down"),
                           ("okay crawl on all fours now", "Crawl on all fours"), ("now just turn around", "Turn Around")):
            self.assertEqual(self.found(text), want, text)

    def test_german_phrases_of_the_builtin_commands(self):
        for text, want in (("kannst du dich hinsetzen", "Sit Down"), ("setz dich bitte", "Sit Down"), ("leg dich hin", "Lay Down"),
                           ("steh auf", "Stand Up"), ("dreh dich um", "Turn Around"), ("bück dich", "Bend Over"),
                           ("leg dich auf den bauch", "Prone")):
            self.assertEqual(self.found(text), want, text)

    def test_whole_words_only_and_negations(self):
        for text in ("I like sitting down", "stand upstairs", "sitdown", "don't sit down", "do not sit down", "never stand up",
                     "please don't turn around", "setz dich nicht hin", "nicht hinsetzen", "no sit down",
                     "", "hello there", None):
            self.assertIsNone(self.found(text), repr(text))

    def test_longest_command_wins_then_the_later_one(self):
        self.assertEqual(self.found("leg dich auf den bauch"), "Prone", "3 words beat 2")
        self.assertEqual(self.found("sit down and then stand up"), "Stand Up", "same length: the later one")

    def test_rest_decides_whether_the_ai_hears_the_sentence(self):
        self.assertEqual(self.v.find("please sit down now")[1], 0)
        self.assertGreaterEqual(self.v.find("can you sit down and tell me about your day")[1], pose_commands.REST_FOR_AI)

    def test_exact_match_and_the_csharp_twin_are_unchanged(self):
        for text in NEAR_MISSES:
            self.assertIsNone(self.v.match(text), repr(text))
        self.assertIn("No substring, word or fuzzy match in `match`", pose_commands.__doc__)

    def test_builtin_rule(self):
        self.assertTrue(pose_commands.is_builtin({"command": "Sit Down", "pose": "Sit Down"}))
        self.assertTrue(pose_commands.is_builtin({"command": "sit down", "pose": "Sit_Down"}))
        self.assertFalse(pose_commands.is_builtin({"command": "Sit Down", "pose": "sitting"}), "relinked by the user")
        self.assertFalse(pose_commands.is_builtin({"command": "Have a seat", "pose": "Have a seat"}))
        self.assertFalse(pose_commands.is_builtin({"command": "Sit Down", "pose": "Custom/Atom/Person/Pose/x.vap"}))
        cs = method_body(src("PoseVocabulary.cs"), "public static bool IsBuiltIn(PoseCommand entry)")
        for part in ("IsPosePath(entry.Pose)", "PoseKey(entry.Pose) != key", "StarterCommands"):
            self.assertIn(part, cs)


class SentenceChainTests(tpc.Chain):
    def test_pose_and_the_rest_of_the_sentence_to_the_ai(self):
        self.start(poses=pose_commands.STARTER_COMMANDS)
        self.ask("Can you sit down and tell me about your day?")
        self.assertEqual([p["json"] for p in self.poses_sent()], ['{"pose":"Sit Down"}'])
        self.assertEqual(len(self.requests()), 1, "the rest of the sentence is conversation")

    def test_command_with_fillers_only_is_just_the_command(self):
        self.start(poses=pose_commands.STARTER_COMMANDS)
        self.ask("Kannst du dich bitte hinsetzen?")
        self.assertEqual([p["json"] for p in self.poses_sent()], ['{"pose":"Sit Down"}'])
        self.assertEqual(self.requests(), [])

    def test_remote_control_stays_exact(self):
        self.start(poses=pose_commands.STARTER_COMMANDS)
        ok, _ = self.app.pose_command("please sit down")
        self.assertFalse(ok)
        self.assertEqual(self.poses_sent(), [])


for _name in [n for n in dir(tpc.Chain) if n.startswith("test_")]:
    setattr(SentenceChainTests, _name, None)   # only the tests of this file (Chain's own run in test_pose_commands)


class RealtimeAndPluginTests(unittest.TestCase):
    def test_realtime_keeps_the_answer_when_there_is_more_to_say(self):
        rt = (ROOT / "companion" / "aibody_companion" / "realtime_voice.py").read_text(encoding="utf-8")
        body = rt[rt.index("def _pose_command"):rt.index("def _mute_command")]
        self.assertLess(body.index("if decision.also_for_ai:"), body.index('self.client.send({"type": "response.cancel"})'))

    def test_substitute_pose_in_the_plugin(self):
        pose = method_body(src("PoseController.cs"), "public string ApplyPoseJson(string json)")
        self.assertIn("SubstituteFor != null && PoseVocabulary.IsBuiltIn(entry)", pose)
        body = src("Body.cs")
        self.assertIn("_poses.SubstituteFor = SubstitutePose;", body)
        sub = method_body(body, "public string SubstitutePose(PoseCommand entry)")
        self.assertIn("_idlePoses.WithoutLast(_idlePoses.Pool(", sub, "random of the idle pool, not the pose shown last")
        self.assertIn("PoseFileProblem", sub)
        self.assertIn("IdlePoseScheduler.ResolveName(", sub, "else the Idle default pose")
        self.assertIn("Log.Info(", sub)
        self.assertIn("used '\" + _poses.LastJsonPose + \"' instead (substitute)", body, "status line names the pose")
        menu = method_body(body, "private void ApplyPoseCommand(string command)")
        self.assertIn("PoseVocabulary.IsBuiltIn(entry)", menu, "Apply Pose uses the substitute too")
        self.assertIn("uses another pose (substitute)", body)


class NoEmptyDropdownTests(unittest.TestCase):
    def test_pose_command_gets_the_first_command(self):
        refresh = method_body(src("Body.cs"), "public void RefreshCharacterChoices()")
        self.assertIn("_poseCommandChoiceJson.val = commands.Count > 0 ? commands[0] : \"\";", refresh)
        self.assertIn("if (_syncingPoseMenu || string.IsNullOrEmpty(command)) return;",
                      method_body(src("Body.cs"), "private void OnPoseCommandChosen(string command)"), "choosing applies nothing")

    def test_gender_not_set(self):
        w = src("CharacterWizard.cs")
        self.assertIn('public const string NotSet = "Not set";', w)
        self.assertIn("genders, NotSet, AiGenderLabel", w)
        self.assertIn("genders, NotSet, UserGenderLabel", w)
        self.assertNotIn('genders.Add("");', w)
        self.assertIn("if (value == Female || value == Male) return value;", w, "config.json still gets \"\" for Not set")

    def test_thrust_control_none(self):
        t = src("DmThrustController.cs")
        self.assertIn('public const string NoThrustTarget = "None";', t)
        self.assertIn("GetAnimationPatternNames(), NoThrustTarget,", t)
        self.assertNotIn('list.Insert(0, "");', t)

    def test_every_chooser_has_a_default_or_is_filled(self):
        # choosers created with "" are filled by RefreshCharacterChoices (SetMenu: first entry)
        body = src("Body.cs")
        for name in ("_expressionChoiceJson", "_gestureChoiceJson"):
            self.assertIn(f"SetMenu({name},", body)


if __name__ == "__main__":
    unittest.main()
