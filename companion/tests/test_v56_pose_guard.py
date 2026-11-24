"""Version 56 (Don, voice 24.11.2026 15:27-15:30, explicit go): one position-preserving wrapper for every pose change
(PoseGuard), pose commands from the companion (voice / typed / tool) through the same path as Apply Pose, the Idle Poser
no longer stops for good after an error, Reset to Default resets Dollmaster too, Dollmaster off restores Auto
Expressions, and no xAI realtime session while VaM is not connected."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from aibody_companion import orchestrator as orch

from .test_plugin_menu import method_body
from .test_realtime import RealtimeSim

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def guard_class() -> str:
    pose = src("PoseController.cs")
    i = pose.index("public class PoseGuard")
    return pose[i:pose.index("public static class BodyMover") if "public static class BodyMover" in pose else i + 7000]


class PoseGuardTests(unittest.TestCase):
    def test_capture_load_put_back(self):
        g = guard_class()
        around = method_body(g, "public string Around(string what, Func<string> load, Atom partner)")
        self.assertLess(around.index("Begin(what);"), around.index("result = load();"))
        self.assertLess(around.index("result = load();"), around.index("Hold();"))
        self.assertIn("finally", around, "she is put back even when the load throws")
        begin = method_body(g, "public void Begin(string what)")
        self.assertIn("if (!Active)", begin, "a pose change during a running guard keeps the first (right) place")
        self.assertIn("_pos = _atom.mainController.transform.position;", begin)
        self.assertIn("_rot = _atom.mainController.transform.rotation;", begin)
        hold = method_body(g, "public void Hold()")
        self.assertIn("BodyMover.Moved(_atom, _pos, _rot)", hold)
        self.assertIn("BodyMover.Relocate(_atom, _pos, _rot);", hold, "position AND rotation are kept, rigid move")
        self.assertNotIn("WriteAllText", g, "pose files are never changed")

    def test_timing_over_frames(self):
        g = guard_class()
        self.assertIn("public const float MinSeconds = PoseController.SettleSeconds + 0.5f;", g)
        self.assertIn("public const float QuietSeconds = 0.5f;", g)
        self.assertIn("public const float MaxSeconds = 5f;", g)
        self.assertIn("if ((_age >= MinSeconds && _quiet >= QuietSeconds) || _age >= MaxSeconds) _age = -1f;", g)
        self.assertIn("Guard.Update(dt);", method_body(src("PoseController.cs"), "public void Update(float dt)"))
        self.assertIn("public void Rebase()", g)

    def test_partner_gets_the_same_correction(self):
        around = method_body(guard_class(), "public string Around(string what, Func<string> load, Atom partner)")
        self.assertIn("Quaternion back = fromRot * Quaternion.Inverse(t.rotation);", around)
        self.assertIn("BodyMover.Relocate(partner, fromPos + back * (p.position - t.position), back * p.rotation);", around)


class EveryPosePathTests(unittest.TestCase):
    def test_pose_file_loads_go_through_the_guard(self):
        pose = src("PoseController.cs")
        load = pose[pose.index("public string LoadPose("):]
        load = load[:load.index("private void StartCheck")]
        self.assertLess(load.index("Guard.Around("), load.index('presets.CallAction("LoadPreset")'))
        # LoadPreset is called nowhere else (menu, idle, default pose, companion commands all end in LoadPose)
        self.assertEqual(pose.count('presets.CallAction("LoadPreset");'), 1)
        for name in ("Body.cs", "AIBody.cs", "CommandRouter.cs", "DmPlugin.cs", "DmMontageController.cs", "DmPoseController.cs"):
            self.assertNotIn("CallAction(\"LoadPreset\")", src(name), name)

    def test_montage_goes_through_the_guard(self):
        m = src("DmMontageController.cs")
        self.assertIn('guard.Around("Dollmaster montage", load, person2Pose != null ? otherPerson : null);', m)
        self.assertLess(m.index("Func<string> load = () =>"), m.index("atom.RestoreTransform(person1Pose);"))
        self.assertIn("_dm.PlaceGuard = () => _body != null ? _body.PoseGuard : null;", src("AIBody.cs"))

    def test_deliberate_moves_rebase(self):
        body = src("Body.cs")
        self.assertGreaterEqual(body.count("_poses.Guard.Rebase();"), 3)


class CompanionPoseCommandTests(unittest.TestCase):
    def test_router_uses_the_body_path(self):
        router = src("CommandRouter.cs")
        self.assertIn("public Func<string, string> ApplyPoseFromCompanion;", router)
        self.assertIn("ApplyPoseFromCompanion != null ? ApplyPoseFromCompanion(json) : _poses.ApplyPoseJson(json)", router)
        self.assertIn("_router.ApplyPoseFromCompanion = ApplyCompanionPose;", src("Body.cs"))

    def test_apply_companion_pose(self):
        body = method_body(src("Body.cs"), "public string ApplyCompanionPose(string json)")
        self.assertIn("_poses.ApplyPoseJson(json)", body)
        self.assertIn("NoteUserPose", body)
        self.assertLess(body.index("_poses.ApplyPoseJson(json)"), body.index("NoteUserPose"))
        self.assertIn("Dollmaster", body, "refused while Dollmaster poses the body")

    def test_no_idle_note_for_failed_commands(self):
        handle = src("Body.cs")
        self.assertNotRegex(handle, r"CmdPose[^\n]*\n[^\n]*NoteUserPose")


class IdlePoserTests(unittest.TestCase):
    """Version 57 (Don 15:57) replaces v56's 30 s pause: a failing pose is dropped from the idle pool at once (first
    failure, for the session) and the next one is picked and loaded right away; the idle poses are never switched off.
    The scheduler behaviour runs for real in test_version35.IdlePoseSchedulerTests (dotnet harness)."""

    def test_failure_drops_the_file_and_goes_on_at_once(self):
        body = method_body(src("Body.cs"), "private void UpdateIdlePoses(float dt, bool speaking)")
        self.assertNotIn("_idlePosesBroken", src("Body.cs"), "root cause: one exception stopped idle poses for the session")
        self.assertNotIn("IdleRetrySeconds", src("Body.cs"), "no 30 s pause any more")
        self.assertNotIn("_idleRetryIn", src("Body.cs"))
        fail = body[body.index("_idlePoses.Exclude(pose);"):]
        self.assertIn("_idleNextNow = true;", fail[:300])
        self.assertIn("failed and is dropped from the idle pool for this session", fail)
        self.assertIn("IdlePoseFile(pose)", fail, "the warning names the file")
        self.assertIn("_idlePoses.PickNow(", body, "the next pose without the wait / cooldown")
        self.assertIn("if (busy) return;", body, "not while someone speaks")

    def test_no_loop_when_everything_fails(self):
        body = method_body(src("Body.cs"), "private void UpdateIdlePoses(float dt, bool speaking)")
        self.assertIn("if (_idlePoses.PoolSize == 0 && _idlePoses.ExcludedCount > 0 && !_idleEmptyLogged)", body)
        self.assertIn("no pose left in the idle pool", body)
        catch = body[body.rindex("catch (Exception e)"):]
        self.assertIn("if (text != _idleLastError)", catch, "an unexpected error is logged once and they go on")
        self.assertNotIn("return", catch)
        pick = method_body(src("IdlePoses.cs"), "public string PickNow(PoseVocabulary vocabulary, List<string> poolNames, List<string> allNames)")
        self.assertIn("if (candidates.Count == 0)", pick)
        self.assertIn("return PickNow(vocabulary, poolNames, allNames);", src("IdlePoses.cs"))


class DollmasterResetTests(unittest.TestCase):
    def test_reset_to_default_resets_dollmaster(self):
        reset = method_body(src("AIBody.cs"), "private void ConfirmReset()")
        self.assertIn("changed += _dm.ResetToDefaults();", reset)
        self.assertIn("_dmActivateJson.val = false;", reset)
        dm = method_body(src("DmPlugin.cs"), "public int ResetToDefaults()")
        self.assertIn("choices", dm, "a chooser never gets a value missing from its list (no empty dropdown)")

    def test_auto_expressions_restored(self):
        dm = src("DmPlugin.cs")
        self.assertIn('auto.SetBoolParamValue("enabled", _savedAutoExpressions);', dm)
        self.assertLess(dm.index("_savedAutoExpressions = autoOn.val;"), dm.index('auto.SetBoolParamValue("enabled", _savedAutoExpressions);'))


class RealtimeWithoutVamTests(RealtimeSim):
    def test_closes_when_vam_is_gone_and_reopens(self):
        self.start()
        self.connect()
        self.assertIsNotNone(self.app.realtime)
        self.app._disconnected_at = self.clock() - orch.REALTIME_CLOSE_AFTER_S - 1
        self.app._update_mode()
        self.assertIsNone(self.app.realtime, "no xAI session (credits) without VaM")
        self.assertIn("Realtime closed: VaM", self.app.mode_note)
        self.app._disconnected_at = None
        self.connect()
        self.assertIsNotNone(self.app.realtime)

    def test_short_gap_keeps_the_session(self):
        self.start()
        self.connect()
        self.app._disconnected_at = self.clock() - 2.0
        self.app._update_mode()
        self.assertIsNotNone(self.app.realtime)
        self.app._disconnected_at = None

    def test_not_opened_when_vam_never_connects(self):
        self.start()
        self.app._ever_connected = False
        self.app._started_at = self.clock() - orch.REALTIME_WAIT_FOR_VAM_S - 1
        want, note = self.app._want_realtime() if not self.app.transport.connected else (False, "Realtime waiting for VaM")
        self.assertFalse(want)
        self.assertIn("Realtime waiting for VaM", note)


if __name__ == "__main__":
    unittest.main()
