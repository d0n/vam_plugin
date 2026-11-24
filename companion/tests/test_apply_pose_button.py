"""Button "Apply Pose" (Don, 22.11.2026 call): the command chosen in "Pose command" is applied at once, also again
(choosing the same entry in the menu fires no callback). Choosing still applies; the help is in the left field."""
from __future__ import annotations

import unittest
from pathlib import Path

from tests.test_plugin_menu import method_body

BODY = (Path(__file__).resolve().parents[2] / "src" / "AIBody" / "Body.cs").read_text(encoding="utf-8")


class ApplyPoseButtonTests(unittest.TestCase):
    def test_button_right_below_the_menu(self):
        tab = method_body(BODY, "public void BuildCharacterTab(UiPage page)")
        self.assertIn('page.Button("Apply Pose", ApplyPoseCommandNow);', tab)
        self.assertLess(tab.index("ScrollablePopup(_poseCommandChoiceJson)"), tab.index('"Apply Pose"'))
        self.assertLess(tab.index('"Apply Pose"'), tab.index('"Add Pose"'))

    def test_same_path_as_choosing(self):
        now = method_body(BODY, "private void ApplyPoseCommandNow()")
        self.assertIn("ApplyPoseCommand(command);", now)
        self.assertIn("choose the command in <b>Pose command</b> first", now)
        chosen = method_body(BODY, "private void OnPoseCommandChosen(string command)")
        self.assertNotIn("ApplyPoseCommand(command);", chosen, "version 52: choosing only selects, Apply Pose applies")
        apply = method_body(BODY, "private void ApplyPoseCommand(string command)")
        for part in ("_poses.Vocabulary.Match(command)", "PoseVocabulary.Resolve(entry, _poses.PoseNames)",
                     "_poses.ApplyPose(pose)", "_idlePoses.NoteUserPose()"):
            self.assertIn(part, apply)

    def test_help_in_the_left_field(self):
        self.assertIn("<b>Apply Pose</b> applies", BODY)
