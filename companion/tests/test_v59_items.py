"""Version 59 (explicit go, 24.11.2026 23:58): (1) one "Idle pose interval (s)" slider (+/- 25 % jitter, old min/max
migrated to their mean), (2) the fixed English built-in pose commands (lie down = Lay Down, kneel down = Get On Your
Knees; v58 in-sentence matching kept), (3) one failover for every pose command (missing or broken pose file -> random
idle-pool pose, else the Idle default pose; no "unavailable" state), (4) no German phrase aliases, (5) the name
replacement in the tree."""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from aibody_companion import pose_commands, settings_file
from aibody_companion.pose_commands import PoseVocabulary

from .test_plugin_menu import method_body
from . import test_pose_commands as tpc

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
BUILTINS = ["Sit Down", "Lay Down", "Turn Around", "Stand Up", "Prone", "Crawl", "Get On Your Knees", "Handstand",
            "Headstand", "Stand On Your Right Leg", "Stand On Your Left Leg"]
OLD = ["Sit Down", "Lay Down", "Prone", "Stand Up", "Spread Your Legs", "Ankle Your Knees", "Ankle Your Elbows",
       "Turn Around", "Crawl on all fours", "Bend Over"]


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def entries(names):
    return [{"command": n, "pose": n} for n in names]


# -- (1) idle pose interval -----------------------------------------------------------------------------------------

class IdleIntervalTests(unittest.TestCase):
    def test_scheduler_has_one_interval_with_25_percent_jitter(self):
        text = src("IdlePoses.cs")
        for part in ("public const float DefaultIntervalSeconds = 165f;", "public const float Jitter = 0.25f;",
                     "public float IntervalSeconds = DefaultIntervalSeconds;", "(1f - Jitter)", "(1f + Jitter)",
                     "public static float MigrateInterval(float minSeconds, float maxSeconds)"):
            self.assertIn(part, text, part)
        self.assertNotIn("public float MinSeconds", text)
        self.assertNotIn("public float MaxSeconds", text)

    def test_menu_shows_only_the_interval_slider(self):
        body = src("Body.cs")
        tab = method_body(body, "public void BuildCharacterTab(UiPage page)")
        self.assertIn("page.Slider(_idlePoseIntervalJson);", tab)
        self.assertNotIn("_idlePoseMinJson", tab)
        self.assertNotIn("_idlePoseMaxJson", tab)
        self.assertIn('IdleIntervalLabel = "Idle pose interval (s)"', body)
        self.assertIn("SettingsDefaults.Float(_plugin, _idlePoseIntervalJson);", body)
        self.assertLess(body.index("SettingsDefaults.Float(_plugin, _idlePoseIntervalJson);"),
                        body.index("_plugin.RegisterFloat(_idlePoseMinJson);"), "old values restore after the interval")

    def test_config_reads_the_interval_and_migrates_old_keys(self):
        body = src("Body.cs")
        self.assertIn('body["idle_pose_interval_s"].AsFloat = _idlePoseIntervalJson.val;', body)
        self.assertNotIn('body["idle_pose_min_s"].AsFloat', body, "old keys are not written any more")
        apply = body[body.index('Protocol.Has(body, "idle_pose_interval_s")') - 200:]
        self.assertIn("IdlePoseScheduler.MigrateInterval(", apply[:1200])

    def test_companion_migrates_old_min_max_to_their_mean(self):
        for given, want in (({"idle_pose_min_s": 60, "idle_pose_max_s": 120}, 90.0),
                            ({"idle_pose_min_s": 30, "idle_pose_max_s": 300}, 165.0),
                            ({"idle_pose_min_s": 600}, 450.0),                    # missing max = the old default 300
                            ({"idle_pose_min_s": 5, "idle_pose_max_s": 10}, 7.5),    # version 66: the floor is 5 s, so the mean 7.5 stays
                            ({"idle_pose_min_s": 1, "idle_pose_max_s": 2}, 5.0),     # clamped to the 5 s floor (30 s up to v65)
                            ({"idle_pose_interval_s": 77, "idle_pose_min_s": 1000, "idle_pose_max_s": 2000}, 77.0),
                            ({}, 165.0)):
            result, _ = settings_file.validate({"body": dict(given)})
            self.assertEqual(result["body"]["idle_pose_interval_s"], want, given)
            self.assertNotIn("idle_pose_min_s", result["body"])
            self.assertNotIn("idle_pose_max_s", result["body"])

    def test_schema_and_example(self):
        schema = json.loads((ROOT / "protocol/schema/config.schema.json").read_text(encoding="utf-8"))
        body = schema["properties"]["body"]["properties"]
        self.assertIn("idle_pose_interval_s", body)
        self.assertNotIn("idle_pose_min_s", body)
        self.assertIn("25 %", body["idle_pose_interval_s"]["description"])


class IdleIntervalHarnessTests(unittest.TestCase):
    """The real C# scheduler (csharp_idle_harness): each wait is within interval +/- 25 %."""

    @classmethod
    def setUpClass(cls):
        from .test_version35 import IdlePoseSchedulerTests
        IdlePoseSchedulerTests.setUpClass()
        cls.sched = IdlePoseSchedulerTests

    @classmethod
    def tearDownClass(cls):
        cls.sched.tearDownClass()

    def gaps(self, **kw):
        runner = self.sched("run_case")
        chosen = runner.run_case([[1.0, False, True, "", 6000]], **kw)
        steps = [int(i) for i, _ in chosen]
        return [b - a for a, b in zip([-1] + steps, steps)]

    def test_jitter_range(self):
        gaps = self.gaps(interval=200)
        self.assertTrue(all(150 <= g <= 251 for g in gaps), gaps)
        self.assertGreater(len(set(gaps)), 3, "random, not fixed")

    def test_old_scene_values_become_the_mean(self):
        gaps = self.gaps(lo=100, hi=300)   # mean 200
        self.assertTrue(all(150 <= g <= 251 for g in gaps), gaps)


# -- (2) + (4) built-in commands, English only ----------------------------------------------------------------------

class BuiltInCommandTests(unittest.TestCase):
    def setUp(self):
        self.v = PoseVocabulary(pose_commands.starter_entries())

    def found(self, text):
        entry, _ = self.v.find(text)
        return entry["command"] if entry else None

    def test_the_fixed_english_set_in_both_languages(self):
        self.assertEqual(list(pose_commands.STARTER_COMMANDS), BUILTINS)
        cs = src("PoseVocabulary.cs")
        block = cs[cs.index("public static readonly string[] StarterCommands"):cs.index("};", cs.index("public static readonly string[] StarterCommands"))]
        self.assertEqual([x for x in block.split('"')[1::2]], BUILTINS, "C# and Python lists are identical")

    def test_each_builtin_and_both_aliases(self):
        for command in BUILTINS:
            self.assertEqual(self.found(command.lower()), command)
            self.assertEqual(self.found("please " + command.lower() + " now"), command, "in-sentence matching kept")
        self.assertEqual(pose_commands.STARTER_ALIASES, {"Lay Down": ("Lie Down",), "Get On Your Knees": ("Kneel Down",)})
        for text, want in (("lie down", "Lay Down"), ("could you lie down please", "Lay Down"), ("kneel down", "Get On Your Knees"),
                           ("now kneel down for me", "Get On Your Knees"), ("stand on your right leg", "Stand On Your Right Leg"),
                           ("Stand on your LEFT leg!", "Stand On Your Left Leg"), ("do a handstand", "Handstand")):
            self.assertEqual(self.found(text), want, text)

    def test_v58_rules_kept_whole_words_negations_longest(self):
        for text in ("don't lie down", "never kneel down", "please don't crawl", "no handstand", "crawling", "headstands",
                     "stand upright", "sit downstairs"):
            self.assertIsNone(self.found(text), text)
        self.assertEqual(self.found("stand up and then stand on your left leg"), "Stand On Your Left Leg", "longest wins")
        self.assertEqual(self.found("crawl and then prone"), "Prone", "same length: the later one")

    def test_no_german_phrases(self):
        for aliases in pose_commands.STARTER_ALIASES.values():
            for alias in aliases:
                self.assertTrue(alias.isascii(), alias)
        for text in ("kannst du dich hinsetzen", "setz dich", "leg dich hin", "steh auf", "dreh dich um", "knie dich hin",
                     "leg dich auf den bauch", "bück dich"):
            self.assertIsNone(self.found(text), text)
        self.assertNotIn("hinsetzen", (ROOT / "companion/aibody_companion/pose_commands.py").read_text(encoding="utf-8"))

    def test_old_starters_migrate_to_the_new_set(self):
        own = {"command": "Wave Hello", "pose": "wave"}
        relinked = {"command": "Bend Over", "pose": "my_bend"}
        migrated = pose_commands.migrate_builtins(entries(OLD) + [own, relinked])
        self.assertEqual([e["command"] for e in migrated],
                         ["Sit Down", "Lay Down", "Prone", "Stand Up", "Turn Around", "Wave Hello", "Bend Over",
                          "Crawl", "Get On Your Knees", "Handstand", "Headstand", "Stand On Your Right Leg", "Stand On Your Left Leg"])
        self.assertIn(relinked, migrated, "a starter the user re-linked is kept")
        self.assertEqual(pose_commands.migrate_builtins([own]), [own], "no old starters: unchanged")
        result, _ = settings_file.validate({"poses": {"commands": entries(OLD)}})
        self.assertEqual(sorted(e["command"] for e in result["poses"]["commands"]), sorted(BUILTINS))
        self.assertIn("v.MigrateBuiltIns()", method_body(src("Body.cs"), "public void LoadPoseCommands(JSONClass root)"))


class CSharpMigrationTests(tpc.RealPoseVocabularyTests):
    def test_csharp_migration_matches_the_companion(self):
        steps = [["clear"]] + [["add", c, c] for c in OLD] + [["add", "Wave Hello", "wave"], ["add", "Bend Over", "my_bend"],
                                                               ["migrate"], ["migrate"]]
        messages, final = self.run_ops([["script", steps]])[0]
        self.assertEqual(messages[-2:], ["migrated", "unchanged"])
        # adding "Bend Over" again only re-links the existing entry (it keeps its place before Wave Hello)
        python = pose_commands.migrate_builtins(entries(OLD[:-1]) + [{"command": "Bend Over", "pose": "my_bend"},
                                                                     {"command": "Wave Hello", "pose": "wave"}])
        self.assertEqual(final, [f"{e['command']}>{e['pose']}" for e in python])


for _name in [n for n in dir(tpc.RealPoseVocabularyTests) if n.startswith("test_")]:
    setattr(CSharpMigrationTests, _name, None)


# -- (3) one failover for every command -----------------------------------------------------------------------------

class FailoverChainTests(tpc.Chain):
    def test_an_own_command_without_its_pose_is_sent(self):
        self.start(poses=("Prone",), commands=[{"command": "Have a seat", "pose": "sitting"}])
        self.ask("please have a seat")
        self.assertEqual([p["json"] for p in self.poses_sent()], ['{"pose":"sitting"}'], "the plugin substitutes")
        self.assertEqual(self.requests(), [])

    def test_a_builtin_without_its_pose_is_sent(self):
        self.start(poses=())
        self.ask("Headstand")
        self.assertEqual([p["json"] for p in self.poses_sent()], ['{"pose":"Headstand"}'])

    def test_remote_control_runs_any_command(self):
        self.start(poses=(), commands=[{"command": "Have a seat", "pose": "sitting"}])
        self.assertEqual(self.app.pose_command("Have a seat"), (True, ""))


for _name in [n for n in dir(tpc.Chain) if n.startswith("test_")]:
    setattr(FailoverChainTests, _name, None)


class FailoverPluginTests(unittest.TestCase):
    def test_one_failover_in_the_pose_controller(self):
        pc = src("PoseController.cs")
        self.assertIn("return ApplyCommand(entry);", method_body(pc, "public string ApplyPoseJson(string json)"))
        cmd = method_body(pc, "public string ApplyCommand(PoseCommand entry)")
        for part in ("PoseVocabulary.Resolve(entry, PoseNames)", "TryApply(actual)", "OnPoseBroken(actual)",
                     "SubstituteFor(entry)", "TryApply(sub)", "OnPoseBroken(sub)", "MaxSubstituteTries", "LastJsonSubstitute = true;"):
            self.assertIn(part, cmd, part)
        self.assertNotIn("IsBuiltIn", cmd, "custom and built-in alike")
        self.assertIn("PoseFileProblem(name) ?? ApplyPose(name)", method_body(pc, "private string TryApply(string name)"))

    def test_body_drops_broken_files_and_picks_from_the_idle_pool(self):
        body = src("Body.cs")
        self.assertIn("_poses.OnPoseBroken = (string name) =>", body)
        self.assertIn("_idlePoses.Exclude(name);", body)
        sub = method_body(body, "public string SubstitutePose(PoseCommand entry)")
        for part in ("_idlePoses.WithoutLast(_idlePoses.Pool(", "PoseFileProblem", "IdlePoseScheduler.ResolveName("):
            self.assertIn(part, sub)
        self.assertIn("_poses.ApplyCommand(entry)", method_body(body, "private void ApplyPoseCommand(string command)"))

    def test_no_unavailable_state_anywhere(self):
        for f in ("src/AIBody/Body.cs", "src/AIBody/PoseController.cs", "src/AIBody/PoseVocabulary.cs",
                  "companion/aibody_companion/orchestrator.py", "companion/aibody_companion/remote/core.py",
                  "companion/aibody_companion/pose_commands.py"):
            text = (ROOT / f).read_text(encoding="utf-8")
            self.assertNotIn("UNAVAILABLE", text, f)
            self.assertNotIn("is unavailable", text, f)
            self.assertNotIn("poses_unavailable", text, f)
            self.assertNotIn('entry["available"]', text, f)
        self.assertFalse(hasattr(PoseVocabulary, "unavailable"))
        event = json.loads((ROOT / "protocol/schema/event.schema.json").read_text(encoding="utf-8"))
        self.assertNotIn('"available"', json.dumps(event))


# -- (5) name replacement ---------------------------------------------------------------------------------------------

class NameTests(unittest.TestCase):
    def test_no_old_first_name_in_tracked_files(self):
        out = subprocess.run(["git", "grep", "-I", "-i", "-l", "le" + "on"], cwd=ROOT, capture_output=True, text=True)
        # the CI workflow keeps two old comment lines: the push token may not change workflow files (needs the
        # workflow scope); that file is replaced as soon as a push with that scope is possible
        hits = [f for f in out.stdout.splitlines() if f and f != ".github/workflows/companion-windows.yml"]
        self.assertEqual(hits, [], hits)
        self.assertIn(b"\\xff\\xd8not a jpeg", (ROOT / "companion/tests/test_v47_regression.py").read_bytes())


if __name__ == "__main__":
    unittest.main()
