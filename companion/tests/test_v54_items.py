"""Version 54 (Don, voice 23:27-23:31, explicit go): shipped scene without Freeze state, the thumbnail pair with fixed
names in every build, Body position that really moves the whole character and stays put, idle poses only from the AIBody
pose folder (+ linked poses, toggle 'Idle poses from all pose files'), and the speech backlog fixes (stuck clip 3 s,
stale clips dropped, no answer queued behind an unplayed backlog, only the newest answer after a VaM freeze, queued
utterances merged into one turn, info text every 2 s)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from aibody_companion import settings_file
from aibody_companion import orchestrator as orch

from .test_plugin_menu import method_body
from .test_e2e_simulation import Sim
from .fakes import FakeClock, FakePlugin

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
sys.path.insert(0, str(ROOT / "tools"))
import build_var  # noqa: E402


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class SceneGlobalStateTests(unittest.TestCase):
    def test_template_has_no_freeze_state_and_strip_removes_one(self):
        text = (ROOT / "examples" / "scenes" / "AI-Buddy.json").read_text(encoding="utf-8")
        self.assertNotIn('"freeze', text.lower())
        keys = build_var.global_state_keys(text)
        self.assertIn("useSceneLoadPosition", keys)
        self.assertFalse([k for k in keys if "freeze" in k.lower()])
        data = {"freezeAnimation": "true", "atoms": [{"id": "CoreControl", "type": "CoreControl",
                                                      "storables": [{"id": "x", "FreezeSound": "true", "keep": 1}]}]}
        removed = build_var.strip_global_state(data)
        self.assertEqual(sorted(removed), ["/atoms[0]/storables[0]/FreezeSound", "/freezeAnimation"])
        self.assertEqual(data["atoms"][0]["storables"][0], {"id": "x", "keep": 1})

    def test_example_scene_is_stripped(self):
        text = build_var.Path(build_var.__file__).read_text()
        scene = text[text.index("def example_scene("):text.index("def plugin_preset(")]
        self.assertIn("strip_global_state(data)", scene)


class ThumbnailPairTests(unittest.TestCase):
    def make_var(self, tmp: Path, thumb_name: str = build_var.SCENE_THUMB_PATH, same_date: bool = True,
                 content: list | None = None, loose: bool = True) -> Path:
        var = tmp / "d0n.AIBody.99.var"
        jpg = build_var.SCENE_THUMB.read_bytes()
        with zipfile.ZipFile(var, "w") as z:
            z.writestr("meta.json", json.dumps({"contentList": content if content is not None
                                                else [build_var.SCENE_PATH, build_var.SCENE_THUMB_PATH]}))
            z.writestr(zipfile.ZipInfo(build_var.SCENE_PATH, (2026, 11, 22, 23, 40, 0)), "{}")
            z.writestr(zipfile.ZipInfo(thumb_name, (2026, 11, 22, 23, 40, 0) if same_date else (2026, 1, 1, 0, 0, 0)), jpg)
        if loose:
            (tmp / build_var.LOOSE_SCENE).write_text("{}", encoding="utf-8")
            (tmp / build_var.LOOSE_THUMB).write_bytes(jpg)
        return var

    def test_good_pair_passes(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertIsNone(build_var.check_scene_thumbnail(self.make_var(Path(t))))

    def test_every_way_to_lose_the_thumbnail_is_refused(self):
        cases = {"upper case": dict(thumb_name="Saves/scene/AIBody/AI-Buddy.JPG"),
                 "dates": dict(same_date=False), "content list": dict(content=[build_var.SCENE_PATH]),
                 "loose pair": dict(loose=False)}
        for label, kw in cases.items():
            with tempfile.TemporaryDirectory() as t:
                self.assertIsNotNone(build_var.check_scene_thumbnail(self.make_var(Path(t), **kw)), label)

    def test_build_writes_the_pair_with_one_fixed_entry(self):
        text = build_var.Path(build_var.__file__).read_text()
        self.assertIn("thumb_info.compress_type = zipfile.ZIP_STORED", text)
        self.assertIn("zipfile.ZipInfo(SCENE_PATH, stamp)", text)
        self.assertIn("zipfile.ZipInfo(SCENE_THUMB_PATH, stamp)", text)
        self.assertEqual(build_var.SCENE_THUMB_PATH, "Saves/scene/AIBody/AI-Buddy.jpg")
        self.assertEqual(build_var.LOOSE_THUMB, "AI-Buddy.jpg")


class BodyPositionTests(unittest.TestCase):
    def test_rigid_absolute_move_main_controller_first(self):
        pose = src("PoseController.cs")
        rel = method_body(pose, "public static int Relocate(Atom atom, Vector3 wantPos, Quaternion wantRot)")
        self.assertLess(rel.index("pos[i] = all[i].transform.position"), rel.index("main.transform.position = wantPos"))
        self.assertLess(rel.index("main.transform.position = wantPos"), rel.index("c.transform.position = wantPos + delta * (pos[i] - fromPos)"))
        self.assertIn("if (c == null || c == main) continue;", rel)
        self.assertNotIn("c.transform.position + shift", pose, "no relative '+ shift' on top of a moved parent")

    def test_pose_loads_keep_her_place(self):
        # version 56: the v54 TakePlace/GuardPlace became the shared wrapper PoseGuard (test_v56_pose_guard)
        pose = src("PoseController.cs")
        load = pose[pose.index("public string LoadPose("):]
        load = load[:load.index("private void StartCheck")]
        self.assertLess(load.index("if (BeforePoseLoad != null) BeforePoseLoad();"), load.index("Guard.Around("))
        self.assertLess(load.index("Guard.Around("), load.index('presets.CallAction("LoadPreset")'))
        self.assertIn("Guard.Update(dt);", method_body(pose, "public void Update(float dt)"))
        guard = pose[pose.index("public class PoseGuard"):pose.index("public class PoseGuard") + 6000]
        self.assertIn("BodyMover.Relocate(_atom, _pos, _rot);", guard)
        self.assertNotIn("WriteAllText", guard, "the pose files are never changed")

    def test_reset_poses_zeroes_the_sliders(self):
        self.assertIn("_body.ForgetBodyPosition();", method_body(src("AIBody.cs"), "private string ResetPoses()"))


class IdlePoolTests(unittest.TestCase):
    def test_pool_from_aibody_folder_plus_linked_and_toggle(self):
        body = src("Body.cs")
        # version 66: the toggle became the menu "Idle pose pool" (test_version66.py)
        self.assertIn("new JSONStorableStringChooser(IdlePoolMode.MenuName", body)
        self.assertIn("SettingsDefaults.Chooser(_plugin, _idlePoolJson);", body)
        self.assertIn("_poses.IdlePoolNames(IdleAllFiles), _poses.PoseNames)", body)
        pose = src("PoseController.cs")
        self.assertIn('public const string OwnPoseFolder = "Custom/Atom/Person/Pose/AIBody";', pose)
        self.assertIn("(allFiles || IsOwnPoseFile(kv.Value))", pose)
        self.assertEqual(settings_file.DEFAULTS["body"]["idle_pose_pool"], "aibody")

    def test_bad_pose_is_dropped(self):
        body = src("Body.cs")
        idle = method_body(body, "private void UpdateIdlePoses(float dt, bool speaking)")
        self.assertIn("_poses.PoseFileProblem(pose) ?? _poses.ApplyPose(pose)", idle)
        self.assertIn("_idlePoses.Exclude(pose);", idle)
        self.assertIn("_bad.Contains(key)", src("IdlePoses.cs"))

    def test_info_does_not_recount_the_pool_every_refresh(self):
        info = method_body(src("Body.cs"), "private string IdlePosesInfo()")
        self.assertIn("if (_poolDirty && _poses != null)", info)


class PluginSpeechBacklogTests(unittest.TestCase):
    def test_stuck_and_stale(self):
        sp = src("SpeechPlayer.cs")
        self.assertIn("public float StuckTimeout = 3f;", sp)
        self.assertIn("public float StaleSeconds = 8f;", sp)
        self.assertIn("u.PlayTime - u.FirstPlayAt > StuckTimeout", sp)
        stale = method_body(sp, "private void DropStale(DateTime now)")
        self.assertIn("if (_current != null && _current.Started) { _lastProgressUtc = now; return; }", stale)
        self.assertIn('Fire(OnEnded, u.Id, "cancelled");', stale)

    def test_ui_refresh_every_two_seconds(self):
        ai = src("AIBody.cs")
        self.assertIn("public const float UiRefreshSeconds = 2f;", ai)
        self.assertIn("if (_uiTimer < UiRefreshSeconds && !opened) return;", ai)


class CompanionBacklogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.sim = Sim(self.tmp.name, self.clock, background=True)
        self.app = self.sim.start_app()
        self.sent: list[dict] = []
        self.app.send = self.sent.append  # type: ignore[method-assign]

    def tearDown(self):
        self.tmp.cleanup()

    def wav(self, name: str) -> Path:
        path = self.app.cfg.audio_abs_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFF")
        return path

    def test_new_answer_replaces_an_unplayed_backlog(self):
        self.app._unstarted = {"old": self.clock() - 10}
        self.app._last_speak_turn = object()
        self.app._queue_speech("utt-new", "Hello", self.wav("utt-new.wav"), 1.0)
        types = [m["type"] for m in self.sent]
        self.assertEqual(types[:2], ["stop_speaking", "speak"])
        self.assertEqual(self.sent[1]["queue"], "interrupt")
        self.assertEqual(list(self.app._unstarted), ["utt-new"])

    def test_answers_append_while_the_plugin_plays(self):
        self.app._unstarted = {"old": self.clock() - 1}
        self.app._queue_speech("utt-2", "Hi", self.wav("utt-2.wav"), 1.0)
        self.assertEqual([m["type"] for m in self.sent], ["speak"])
        self.assertEqual(self.sent[0]["queue"], "append")

    def test_merge_queued_utterances(self):
        gen = self.app._generation
        self.app._jobs.put(("audio", b"\x01\x00" * 100, gen, 5.0))
        self.app._jobs.put(("audio", b"\x02\x00" * 100, gen, 6.0))
        self.app._jobs.put(("text", "typed", gen, 7.0))
        data, t0 = self.app._merge_queued_audio(b"\x03\x00" * 100, gen, 4.0)
        gap = int(self.app.cfg.sample_rate * orch.MERGE_SILENCE_S) * 2
        self.assertEqual(len(data), 600 + 2 * gap)
        self.assertEqual(t0, 6.0)
        self.assertEqual(self.app._jobs.get_nowait()[0], "text", "other kinds stay queued")

    def test_after_a_freeze_only_the_newest_is_answered(self):
        submitted = []
        self.app._submit = lambda kind, data, t0=None: submitted.append((kind, data))  # type: ignore[method-assign]
        self.app._disconnected_at = self.clock()
        self.assertEqual(self.app.handle_utterance(b"\x01\x00" * 10), "")
        self.app.handle_utterance(b"\x02\x00" * 10)
        self.assertEqual(submitted, [], "held while the plugin is away")
        self.app._queue_speech("utt-x", "late", self.wav("utt-x.wav"), 1.0)
        self.assertFalse([m for m in self.sent if m["type"] == "speak"], "no speech into the inbox of a frozen VaM")
        self.app._disconnected_at = None
        self.app._after_gap(12.0)
        self.assertIn("stop_speaking", [m["type"] for m in self.sent])
        self.assertEqual(submitted, [("audio", b"\x02\x00" * 10)])


class DocsTests(unittest.TestCase):
    def test_test_protocol_and_spec(self):
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        for step in ("T89", "T90", "T91", "T92"):
            self.assertIn(step, proto)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 54, release", spec)


if __name__ == "__main__":
    unittest.main()
