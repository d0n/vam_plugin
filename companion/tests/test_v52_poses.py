"""Version 52 (Don, 22.11.2026 20:47-20:48): pose commands and Apply Pose, the twitching, the pose menu race.
Root causes and fixes: the pose was loaded twice (VaM's Load On Select + LoadPreset), the idle head / chest motion went on
writing the controllers while VaM applied the pose (two writers = twitching), Body control was saved as OFF after
Dollmaster had been active (voice pose commands then went to the chat), the Pose command menu applied on choosing (choosing
the same entry again fires nothing), and .json files were listed as poses though PosePresets loads only .vap presets."""
from __future__ import annotations

import unittest

from .test_plugin_menu import method_body, source


class LoadOnceTests(unittest.TestCase):
    def setUp(self):
        self.pc = source("PoseController.cs")
        self.load = method_body(self.pc, "public string LoadPose(string path)")

    def test_load_on_select_is_off_while_the_path_is_set_and_put_back(self):
        load = self.load
        self.assertIn('presets.GetBoolJSONParam("loadPresetOnSelect")', load)
        off = load.index("onSelect.val = false;")
        self.assertLess(off, load.index("url.val = SuperController.singleton.NormalizePath(path);"))
        self.assertLess(load.index("url.val = SuperController.singleton.NormalizePath(path);"), load.index('presets.CallAction("LoadPreset");'))
        self.assertEqual(load.count('presets.CallAction('), 1, "one load, not two")
        self.assertIn("finally", load)
        self.assertIn("onSelect.val = true;", load[load.index("finally"):])

    def test_the_idle_motion_holds_before_the_load(self):
        self.assertLess(self.load.index("BeforePoseLoad()"), self.load.index('presets.CallAction("LoadPreset");'))
        body = source("Body.cs")
        # version 64: the idle movement (v60-v63) is removed; the hook only holds the idle motion
        self.assertIn("_poses.BeforePoseLoad = () =>\n                {\n                    if (_idle != null) _idle.HoldForPose(PoseController.SettleSeconds);\n                };", body)
        idle = source("IdleController.cs")
        hold = method_body(idle, "public void HoldForPose(float seconds)")
        self.assertIn("RestoreNow();", hold, "the offsets come off BEFORE VaM stores / applies the pose")
        update = method_body(idle, "public string Update(float deltaTime, bool speaking, float breathCycle, float breathDepth)")
        self.assertLess(update.index("if (_hold > 0f)"), update.index("ApplyOffset(_head"))
        self.assertIn("return finished;", update[update.index("if (_hold > 0f)"):update.index("ApplyOffset(_head")])

    def test_only_pose_presets(self):
        scan = method_body(self.pc, "public void ScanPoseFiles()")
        self.assertIn('if (!lower.EndsWith(".vap")) continue;', scan)
        self.assertNotIn('EndsWith(".json")', scan)
        self.assertIn('EndsWith(".json")', self.load)
        self.assertIn("not a pose preset (.vap)", self.load)

    def test_the_result_is_checked_after_it_settled(self):
        self.assertIn("public const float SettleSeconds = 1.0f;", self.pc)
        update = method_body(self.pc, "public void Update(float dt)")
        self.assertIn("no controller moved", update)
        self.assertIn("Log.Warn(LastLoadCheck)", update)
        body_update = method_body(source("Body.cs"), "public void Update(")
        self.assertLess(body_update.index("_poses.Update(dt);"), body_update.index("if (DollmasterOwns)"))
        self.assertIn("Last pose load: ", method_body(source("Body.cs"), "public string CharacterInfoText()"))

    def test_the_load_targets_the_ai_person(self):
        body = source("Body.cs")
        self.assertIn("_poses = new PoseController(_atom, _idle);", body)
        self.assertIn("new Body(this, aiAtom ?? containingAtom, SendToApp, _diag)", source("AIBody.cs"))


class BodyControlTests(unittest.TestCase):
    def test_config_keeps_the_users_toggle_not_the_dollmaster_state(self):
        write = method_body(source("Body.cs"), "public void WriteSettings(JSONClass root)")
        self.assertIn('body["body_control"].AsBool = _bodyControlJson == null || _bodyControlJson.val;', write)
        self.assertNotIn('body["body_control"].AsBool = BodyControl;', write)
        status = method_body(source("Body.cs"), "public void AddStatus(JSONClass s)")
        self.assertIn('s["body_control"].AsBool = BodyControl;', status, "the companion still sees the effective state")

    def test_an_ignored_pose_is_logged(self):
        router = source("CommandRouter.cs")
        self.assertIn('Log.Info("Pose ignored: Body control is off or Dollmaster is active")', router)


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.body = source("Body.cs")

    def test_choosing_only_stores_apply_applies(self):
        chosen = method_body(self.body, "private void OnPoseCommandChosen(string command)")
        self.assertNotIn("ApplyPose", chosen)
        self.assertIn("press Apply Pose", chosen)
        self.assertIn("ApplyPoseCommand(command);", method_body(self.body, "private void ApplyPoseCommandNow()"))
        self.assertIn('(string v) => { if (_idlePoses != null) _idlePoses.DefaultPose = IdlePoseScheduler.NameOf(v); _poolDirty = true; }', self.body,
                      "Idle default pose: choosing only stores it (the idle poses use it)")
        self.assertIn("_poses.ApplyPose(pose)", method_body(self.body, "private void ApplyIdleDefaultPose()"))

    def test_dollmaster_poses_the_body_alone(self):
        for sig, call in (("private void ApplyPoseCommand(string command)", "_poses.ApplyCommand(entry)"),   # version 59
                          ("private void ApplyIdleDefaultPose()", "_poses.ApplyPose(pose)")):
            m = method_body(self.body, sig)
            self.assertLess(m.index("if (DollmasterOwns)"), m.index(call), sig)
        self.assertIn("turn Activate off to use pose commands", self.body)

    def test_help_text(self):
        info = method_body(self.body, "private string PoseCommandsInfo()")
        for part in ("only selects it", "<b>Apply Pose</b> applies it", "loaded once", "Dollmaster", "(.vap)"):
            self.assertIn(part, info, part)


if __name__ == "__main__":
    unittest.main()
