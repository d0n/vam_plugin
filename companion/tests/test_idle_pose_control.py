"""Idle pose control in the menu (Leon, 22.11.2026 call). Tab AI Character > Idle poses already had Idle poses (on/off),
Idle default pose, Idle pose min / max wait; new is "Apply idle default pose", which goes to the default pose now."""
from __future__ import annotations

import unittest
from pathlib import Path

from tests.test_plugin_menu import method_body

BODY = (Path(__file__).resolve().parents[2] / "src" / "AIBody" / "Body.cs").read_text(encoding="utf-8")


class IdlePoseControlTests(unittest.TestCase):
    def test_section_order(self):
        tab = method_body(BODY, "public void BuildCharacterTab(UiPage page)")
        order = ['"<b>Idle poses</b>"', "Toggle(_idlePosesJson)", "ScrollablePopup(_idlePoseDefaultJson)",
                 '"Apply idle default pose"', "Slider(_idlePoseMinJson)", "Slider(_idlePoseMaxJson)"]
        positions = [tab.index(x) for x in order]
        self.assertEqual(positions, sorted(positions))

    def test_applies_the_chosen_default_pose(self):
        apply = method_body(BODY, "private void ApplyIdleDefaultPose()")
        for part in ("IdlePoseScheduler.ResolveName(_idlePoseDefaultJson.val, _poses.PoseNames)", "_poses.ApplyPose(pose)",
                     "_idlePoses.NoteUserPose()", "<color=red>"):
            self.assertIn(part, apply)

    def test_help_in_the_left_field(self):
        self.assertIn("<b>Apply idle default pose</b> goes there now", BODY)
