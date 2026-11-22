"""Version 51 (Leon, 22.11.2026 20:38-20:58): idle poses are random of ALL poses (never twice in a row, no forced return
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

    def test_default_wait_is_30_to_300_seconds(self):
        chosen = self.run_case([[1.0, False, True, "", 20000]], lo=30, hi=300)
        steps = [int(i) for i, _ in chosen]
        gaps = [b - a for a, b in zip([-1] + steps, steps)]
        self.assertTrue(all(30 <= g <= 301 for g in gaps), gaps)
        self.assertGreater(max(gaps) - min(gaps), 60, "random, not a fixed interval")

    def test_range_is_clamped_to_30_and_18000_and_min_above_max_is_swapped(self):
        chosen = self.run_case([[1.0, False, True, "", 400]], lo=1, hi=5)
        steps = [int(i) for i, _ in chosen]
        self.assertTrue(all(g >= 30 for g in [b - a for a, b in zip([-1] + steps, steps)]))
        self.assertEqual(self.run_case([[10.0, False, True, "", 1700]], lo=99999, hi=99999), [], "18000 s max: not in 17000 s")
        self.assertEqual(len(self.run_case([[10.0, False, True, "", 1810]], lo=99999, hi=99999)), 1)
        chosen = self.run_case([[1.0, False, True, "", 2000]], lo=200, hi=100)
        gaps = [b - a for a, b in zip([-1] + [int(i) for i, _ in chosen], [int(i) for i, _ in chosen])]
        self.assertTrue(all(100 <= g <= 201 for g in gaps), gaps)

    def test_timer_runs_only_while_idle(self):
        self.assertEqual(self.run_case([[1.0, True, True, "", 2000]], lo=30, hi=30), [], "someone speaks all the time")
        self.assertEqual(self.run_case([[1.0, False, False, "", 2000]], lo=30, hi=30), [],
                         "Body control off (BodyControl is false while Dollmaster owns the body)")


class PluginWiringTests(unittest.TestCase):
    def test_scheduler_constants_and_pool(self):
        text = source("IdlePoses.cs")
        for part in ("DefaultMinSeconds = 30f", "DefaultMaxSeconds = 300f", "LowestSeconds = 30f", "HighestSeconds = 18000f",
                     "public List<string> Pool(", "WithoutLast(pool)", "public void NoteShown(string pose)", "PoolSize = pool.Count"):
            self.assertIn(part, text, part)
        self.assertNotIn("_inIdlePose", text, "no alternation with the default pose any more")
        self.assertNotIn("Candidates(", text)

    def test_sliders_keep_their_storable_names_and_enforce_min_le_max(self):
        body = source("Body.cs")
        self.assertIn('new JSONStorableFloat("Idle pose min wait (s)", IdlePoseScheduler.DefaultMinSeconds,\n'
                      '                OnIdleMinChanged, IdlePoseScheduler.LowestSeconds, IdlePoseScheduler.HighestSeconds)', body)
        self.assertIn('new JSONStorableFloat("Idle pose max wait (s)", IdlePoseScheduler.DefaultMaxSeconds,\n'
                      '                OnIdleMaxChanged, IdlePoseScheduler.LowestSeconds, IdlePoseScheduler.HighestSeconds)', body)
        self.assertIn("_idlePoseMaxJson.val < v) _idlePoseMaxJson.val = v;", method_body(body, "private void OnIdleMinChanged(float v)"))
        self.assertIn("_idlePoseMinJson.val > v) _idlePoseMinJson.val = v;", method_body(body, "private void OnIdleMaxChanged(float v)"))

    def test_dollmaster_pauses_the_timer(self):
        update = method_body(source("Body.cs"), "public void Update(")
        self.assertLess(update.index("if (DollmasterOwns)"), update.index("UpdateIdlePoses(dt, speaking);"))
        self.assertIn("return;", update[update.index("if (DollmasterOwns)"):update.index("UpdateIdlePoses(dt, speaking);")])

    def test_info_field_and_verbose_log_show_the_pool(self):
        body = source("Body.cs")
        info = method_body(body, "private string IdlePosesInfo()")
        for part in ("control how often the idle pose changes", "_idlePoses.Pool(", "Defaults 30 s and 300 s (5 min)",
                     "range 30 to 18000 s (300 min)", "slider's value field", "body.idle_pose_min_s", "Dollmaster",
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
        self.assertEqual(settings_file.DEFAULTS["body"]["idle_pose_min_s"], 30.0)
        self.assertEqual(settings_file.DEFAULTS["body"]["idle_pose_max_s"], 300.0)
        self.assertEqual(settings_file.RANGES[("body", "idle_pose_min_s")], (30.0, 18000.0))
        self.assertEqual(settings_file.RANGES[("body", "idle_pose_max_s")], (30.0, 18000.0))
        result, _ = settings_file.validate({"body": {"idle_pose_min_s": 17999.5, "idle_pose_max_s": 99999}})
        self.assertEqual(result["body"]["idle_pose_min_s"], 17999.5, "exact values are kept")
        self.assertEqual(result["body"]["idle_pose_max_s"], 18000.0)
        example = json.loads((ROOT / "examples/config.json").read_text(encoding="utf-8"))
        self.assertEqual((example["body"]["idle_pose_min_s"], example["body"]["idle_pose_max_s"]), (30.0, 300.0))


if __name__ == "__main__":
    unittest.main()
