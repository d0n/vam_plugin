"""Version 42 (Leon, 21.11.2026 18:27 and 18:33, his v41 test): the Pose command menu applies on choosing (no Pose
dropdown, no Apply buttons), Add Pose with VaM's file browser + the spoken command, Delete Pose, Reset poses (AI first,
then Client), his scene with AIBody on 'Client' driving 'AI', the realtime answer after a tool-only response, the
scrollable Voice menu, and the companion's warning when the scene loads an older plugin package (every log line of his
v41 test said plugin=40: the scene pinned d0n.AIBody.40, so the v41 audio code never ran in VaM).
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from unittest import TestCase

from aibody_companion import pose_commands, voices
from aibody_companion.orchestrator import version_mismatch

from tests.test_realtime import RealtimeSim

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def method_body(text: str, signature: str) -> str:
    start = text.index(signature)
    i = text.index("{", start)
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    raise AssertionError(signature)


class PoseMenuTests(TestCase):
    def setUp(self):
        self.body = source("Body.cs")
        self.tab = method_body(self.body, "public void BuildCharacterTab(UiPage page)")

    def test_exact_order_of_the_poses_section(self):
        poses = self.tab[self.tab.index('"<b>Poses</b>"'):]
        order = ['"<b>Poses</b>"', "ScrollablePopup(_poseCommandChoiceJson)", '"Apply Pose"', '"Add Pose"', "NewPoseCommandLabel",
                 '"Save pose command"', '"Cancel Add Pose"', '"Delete Pose"', '"Reset poses"', '"Restore starter poses"',
                 '"Reload poses"']
        positions = [poses.index(x) for x in order]
        self.assertEqual(positions, sorted(positions))

    def test_no_pose_dropdown_and_no_apply_buttons(self):
        # the old "Pose" menu and its buttons stay gone; 22.11.2026 brought one "Apply Pose" for the Pose command
        for gone in ("_poseChoiceJson", "Apply pose", "ApplyChosenPose", "ApplyPoseCommandLabel"):
            self.assertNotIn(gone, self.body)

    def test_choosing_a_command_selects_it_with_a_guard(self):
        # version 52 (Leon 20:48): choosing only selects (it applied once and then never again); Apply Pose applies
        self.assertIn("OnPoseCommandChosen", self.body)
        chosen = method_body(self.body, "private void OnPoseCommandChosen(string command)")
        self.assertIn("if (_syncingPoseMenu", chosen)
        self.assertNotIn("ApplyPoseCommand(command)", chosen)
        self.assertIn("_poses.ApplyPose(pose)", method_body(self.body, "private void ApplyPoseCommand(string command)"))
        quiet = method_body(self.body, "private void SelectPoseCommandQuietly(string command)")
        self.assertIn("_syncingPoseMenu = true", quiet)
        self.assertIn("finally", quiet)

    def test_add_pose_uses_the_file_browser_then_the_command_field(self):
        start = method_body(self.body, "private void StartAddPose()")
        self.assertIn("SuperController.singleton.GetMediaPathDialog(OnPoseFileChosen, \"vap\", PoseBrowseFolder, false, true)", start)
        chosen = method_body(self.body, "private void OnPoseFileChosen(string path)")
        self.assertIn("FileManagerSecure.NormalizePath(path)", chosen)
        self.assertIn("_poseCommandTextJson.val", chosen)
        save = method_body(self.body, "private void SaveNewPoseCommand()")
        self.assertIn("PoseCommandsChanged()", save)

    def test_add_delete_restore_persist(self):
        changed = method_body(self.body, "private void PoseCommandsChanged()")
        self.assertIn("OnSettingsChanged", changed)
        for sig in ("private void DeleteChosenPoseCommand()", "private void RestoreStarterPoses()"):
            self.assertIn("PoseCommandsChanged()", method_body(self.body, sig), sig)

    def test_pose_file_paths_resolve_in_both_languages(self):
        vocab = source("PoseVocabulary.cs")
        self.assertIn("public static bool IsPosePath(string", vocab)
        self.assertIn("if (PoseVocabulary.IsPosePath(name)) return LoadPose(name);", source("PoseController.cs"))
        self.assertTrue(pose_commands.is_pose_path("Custom/Atom/Person/Pose/Me/wave.vap"))
        self.assertTrue(pose_commands.is_pose_path("Saves/Person/pose/sit.json"))
        self.assertFalse(pose_commands.is_pose_path("sitting"))

    def test_reset_poses_ai_first_then_client(self):
        plugin = source("AIBody.cs")
        reset = method_body(plugin, "private string ResetPoses()")
        self.assertLess(reset.index("_aiPlacement.Restore()"), reset.index("_clientResetIn = ClientResetDelay"))
        self.assertIn("_clientPlacement.Restore()", method_body(plugin, "private void UpdateClientReset(float dt)"))
        self.assertIn("_body.ResetPosesRequested = ResetPoses;", plugin)
        self.assertIn("public class PlacementSnapshot", source("PoseController.cs"))
        self.assertIn('ResetPosesRequested', method_body(self.body, "private void ResetPoses()"))


class TargetAtomTests(TestCase):
    def test_plugin_on_client_drives_the_ai_atom(self):
        plugin = source("AIBody.cs")
        self.assertIn('public const string AiAtomName = "AI";', plugin)
        self.assertIn('public const string ClientAtomName = "Client";', plugin)
        find = method_body(plugin, "private Atom FindAiCharacter()")
        self.assertIn("SuperController.singleton.GetAtoms()", find)
        self.assertIn('a.type != "Person"', find)
        self.assertIn("new Body(this, aiAtom ?? containingAtom", plugin)
        self.assertIn("_body.SetAtom(ai)", method_body(plugin, "private void UpdateTarget(float dt)"))
        self.assertIn("public void SetAtom(Atom atom)", source("Body.cs"))
        audit = (ROOT / "docs" / "API_AUDIT.md").read_text(encoding="utf-8")
        self.assertIn("| E37 |", audit)

    def test_scene_has_the_plugin_on_client_only(self):
        data = json.loads((ROOT / "examples" / "scenes" / "AI-Buddy.json").read_text(encoding="utf-8"))
        holders = [(a["id"], st["plugins"]) for a in data["atoms"] for st in a["storables"]
                   if st["id"] == "PluginManager" and st["plugins"]]
        self.assertEqual([h for h, _ in holders], ["Client"])
        ids = [a["id"] for a in data["atoms"] if a["type"] == "Person"]
        self.assertEqual(ids, ["AI", "Client"])
        st = next(s for a in data["atoms"] for s in a["storables"] if s["id"] == "plugin#0_AIBody.AIBodyPlugin")
        self.assertEqual(st["Set background color"], "true")
        self.assertNotIn("Settings initialized", st, "a shipped scene must let config.json apply")
        self.assertNotIn("api_key", json.dumps(data).lower())


class VoiceMenuTests(TestCase):
    def test_voice_menu_scrolls_and_lists_all_28(self):
        link = source("AppLink.cs")
        self.assertIn("page.ScrollablePopup(_voiceJson);", link)
        self.assertNotIn("page.Popup(_voiceJson);", link)
        self.assertEqual(len(voices.XAI_VOICES), 28)
        static = re.search(r"XaiVoices\s*=\s*\{([^}]*)\}", link) or re.search(r"XaiVoices\s*=\s*new string\[\]\s*\{([^}]*)\}", link)
        self.assertIsNotNone(static)
        self.assertEqual(len(re.findall(r'"[^"]+"', static.group(1))), 28)
        self.assertIn('SetVoiceChoices(msg["voices"]', method_body(link, "private void HandleCompanionHeartbeat(JSONClass msg)"))


class VersionCheckTests(TestCase):
    def test_older_plugin_package_is_named(self):
        note = version_mismatch("40", "42")
        self.assertIn("d0n.AIBody.40", note)
        self.assertIn("d0n.AIBody.42", note)
        self.assertEqual(version_mismatch("42", "42"), "")
        self.assertEqual(version_mismatch(None, "42"), "")
        self.assertEqual(version_mismatch("test", "42"), "")


class ToolOnlyAnswerTests(RealtimeSim):
    def test_tool_only_answer_asks_once_for_the_spoken_answer(self):
        self.start()
        self.connect()
        self.server.respond([], b"", response_id="r-tool", call={"name": "express", "arguments": {"expression": "happy"}})
        self.assertTrue(self.pump(lambda: "response.create" in self.server.conn.types()))
        self.server.respond([], b"", response_id="r-tool2", call={"name": "express", "arguments": {"expression": "sad"},
                                                                    "call_id": "call-2"})
        self.pump(lambda: self.server.conn.types().count("function_call_output") > 1 or len(self.sim.sent(self.plugin, "expression")) > 1,
                  timeout=2.0)
        self.pump(timeout=0.3)
        self.assertEqual(self.server.conn.types().count("response.create"), 1, "never a loop")
