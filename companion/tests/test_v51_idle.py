"""Version 51 (Don, 22.11.2026 20:38-20:58): idle poses are random of ALL poses (never twice in a row, no forced return
to the default pose), the existing sliders 'Idle pose min wait (s)' / 'Idle pose max wait (s)' with 30 / 300 s and
30-18000 s, min <= max, paused by Dollmaster, pool size in the info field and the verbose log."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from aibody_companion import settings_file

from .test_plugin_menu import method_body, source
from . import test_version35 as v35

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(Path(v35.DOTNET).exists(), "dotnet SDK not installed")
class RandomOfAllPosesTests(unittest.TestCase):
    """The plugin's real IdlePoses.cs in the dotnet harness (same build as version 35, without its tests)."""
    setUpClass = classmethod(v35.IdlePoseSchedulerTests.setUpClass.__func__)
    tearDownClass = classmethod(v35.IdlePoseSchedulerTests.tearDownClass.__func__)
    run_case = v35.IdlePoseSchedulerTests.run_case

    def names(self, **kw):
        steps = kw.pop("steps", [[1.0, False, True, "", 6000]])
        return [n for _, n in self.run_case(steps, **kw)]

    def test_two_pose_ping_pong_is_gone(self):
        # v49: only ONE pose command had a pose file ('Sit Down'), so the character switched Sit Down <-> Stand Up only
        poses = ("Stand Up", "Sit Down", "lean_wall", "arms_crossed", "kneel", "look_away")
        names = self.names(poses=poses)
        self.assertGreater(len(names), 100)
        self.assertEqual(set(names), set(poses), "every pose file is in the pool, not only the pose commands")
        self.assertTrue(all(a != b for a, b in zip(names, names[1:])), "never the same twice in a row")
        self.assertLess(names.count("Stand Up"), len(names) / 3, "no forced return to the default pose")

    def test_one_pose_only_still_works_and_none_gives_nothing(self):
        self.assertEqual(set(self.names(poses=("Stand Up",))), {"Stand Up"})
        self.assertEqual(self.names(poses=()), [])

    def test_default_wait_is_165_seconds_plus_minus_25_percent(self):
        # version 59: one interval (default 165 s = the mean of the old 30 / 300 s defaults), +/- 25 % jitter
        chosen = self.run_case([[1.0, False, True, "", 20000]], interval=165)
        steps = [int(i) for i, _ in chosen]
        gaps = [b - a for a, b in zip([-1] + steps, steps)]
        self.assertTrue(all(123 <= g <= 208 for g in gaps), gaps)
        self.assertGreater(max(gaps) - min(gaps), 20, "random jitter, not a fixed interval")

    def test_interval_is_clamped_to_30_and_18000_and_old_min_max_become_their_mean(self):
        # version 59: the interval is clamped to 30-18000 s before the +/- 25 % jitter
        chosen = self.run_case([[1.0, False, True, "", 400]], interval=1)
        steps = [int(i) for i, _ in chosen]
        self.assertTrue(all(22 <= g <= 38 for g in [b - a for a, b in zip([-1] + steps, steps)]))
        self.assertEqual(self.run_case([[10.0, False, True, "", 1300]], interval=99999), [], "18000 s - 25 %: not in 13000 s")
        self.assertEqual(len(self.run_case([[10.0, False, True, "", 2260]], interval=99999)), 1, "at most 22500 s")
        chosen = self.run_case([[1.0, False, True, "", 2000]], lo=100, hi=200)   # an old scene: mean 150 s
        gaps = [b - a for a, b in zip([-1] + [int(i) for i, _ in chosen], [int(i) for i, _ in chosen])]
        self.assertTrue(all(112 <= g <= 189 for g in gaps), gaps)

    def test_timer_runs_only_while_idle(self):
        self.assertEqual(self.run_case([[1.0, True, True, "", 2000]], lo=30, hi=30), [], "someone speaks all the time")
        self.assertEqual(self.run_case([[1.0, False, False, "", 2000]], lo=30, hi=30), [],
                         "Body control off (BodyControl is false while Dollmaster owns the body)")


class PluginWiringTests(unittest.TestCase):
    def test_scheduler_constants_and_pool(self):
        text = source("IdlePoses.cs")
        for part in ("DefaultIntervalSeconds = 165f", "Jitter = 0.25f", "LowestSeconds = 30f", "HighestSeconds = 18000f",
                     "public List<string> Pool(", "WithoutLast(pool)", "public void NoteShown(string pose)", "PoolSize = pool.Count"):
            self.assertIn(part, text, part)
        self.assertNotIn("_inIdlePose", text, "no alternation with the default pose any more")
        self.assertNotIn("Candidates(", text)

    def test_old_sliders_only_migrate_old_scenes(self):
        # version 59: the v51-v58 storables stay registered (not shown, not saved) so an old scene's values migrate
        body = source("Body.cs")
        self.assertIn('new JSONStorableFloat("Idle pose min wait (s)", IdlePoseScheduler.OldDefaultMinSeconds,', body)
        self.assertIn('new JSONStorableFloat("Idle pose max wait (s)", IdlePoseScheduler.OldDefaultMaxSeconds,', body)
        self.assertIn("_idlePoseMinJson.isStorable = false;", body)
        self.assertNotIn("OnIdleMinChanged", body)
        self.assertIn("IdlePoseScheduler.MigrateInterval(_idlePoseMinJson.val, _idlePoseMaxJson.val)",
                      method_body(body, "private void MigrateIdleInterval()"))

    def test_dollmaster_pauses_the_timer(self):
        update = method_body(source("Body.cs"), "public void Update(")
        self.assertLess(update.index("if (DollmasterOwns)"), update.index("UpdateIdlePoses(dt, speaking);"))
        self.assertIn("return;", update[update.index("if (DollmasterOwns)"):update.index("UpdateIdlePoses(dt, speaking);")])

    def test_info_field_and_verbose_log_show_the_pool(self):
        body = source("Body.cs")
        info = method_body(body, "private string IdlePosesInfo()")
        for part in ("sets how often the ", "_idlePoses.Pool(", "Default 165 s",
                     "range 30 to 18000 s (300 min)", "slider's value field", "body.idle_pose_interval_s", "Dollmaster",
                     "never the same one twice in a row"):
            self.assertIn(part, info, part)
        update = method_body(body, "private void UpdateIdlePoses(float dt, bool speaking)")
        self.assertIn('Log.Debug("Idle pose: " + pose + " (random of a pool of " + _idlePoses.PoolSize + " poses)")', update)
        self.assertIn('if (seconds >= 60f) text += " (" + (seconds / 60f)', method_body(body, "public static string WaitText(float seconds)"))

    def test_pose_commands_and_apply_note_the_shown_pose(self):
        body = source("Body.cs")
        self.assertIn("_idlePoses.NoteShown(pose)", method_body(body, "private void ApplyIdleDefaultPose()"))
        self.assertIn("_idlePoses.NoteShown(pose)", method_body(body, "private void ApplyPoseCommand(string command)"))

    def test_companion_defaults_ranges_and_example(self):
        # version 59: one interval key; old min / max keys become their mean
        self.assertEqual(settings_file.DEFAULTS["body"]["idle_pose_interval_s"], 165.0)
        self.assertNotIn("idle_pose_min_s", settings_file.DEFAULTS["body"])
        self.assertEqual(settings_file.RANGES[("body", "idle_pose_interval_s")], (30.0, 18000.0))
        result, _ = settings_file.validate({"body": {"idle_pose_interval_s": 17999.5}})
        self.assertEqual(result["body"]["idle_pose_interval_s"], 17999.5, "exact values are kept")
        result, _ = settings_file.validate({"body": {"idle_pose_min_s": 17999.5, "idle_pose_max_s": 99999}})
        self.assertEqual(result["body"]["idle_pose_interval_s"], 18000.0)
        example = json.loads((ROOT / "examples/config.json").read_text(encoding="utf-8"))
        self.assertEqual(example["body"]["idle_pose_interval_s"], 165.0)
        self.assertNotIn("idle_pose_max_s", example["body"])


if __name__ == "__main__":
    unittest.main()
