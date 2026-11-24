"""Body position control in the menu (Don, 22.11.2026 call): tab AI Character > Body position moves / turns the whole
AI character (every controller, like Reset poses' PlacementSnapshot), Reset body position takes it back. The sliders
are not registered, so a saved scene never moves her twice."""
from __future__ import annotations

import unittest
from pathlib import Path

from tests.test_plugin_menu import method_body

SRC = Path(__file__).resolve().parents[2] / "src" / "AIBody"
BODY = (SRC / "Body.cs").read_text(encoding="utf-8")
POSE = (SRC / "PoseController.cs").read_text(encoding="utf-8")


class MenuTests(unittest.TestCase):
    def test_section_after_body_control(self):
        tab = method_body(BODY, "public void BuildCharacterTab(UiPage page)")
        order = ['"<b>Body control</b>"', "Toggle(_bodyControlJson)", '"<b>Body position</b>"', "Slider(_moveForwardJson)",
                 "Slider(_moveRightJson)", "Slider(_turnJson)", '"Reset body position"', '"<b>Idle poses</b>"']
        positions = [tab.index(x) for x in order]
        self.assertEqual(positions, sorted(positions))

    def test_sliders_are_not_saved(self):
        for name in ("_moveForwardJson", "_moveRightJson", "_turnJson"):
            self.assertNotIn(f"SettingsDefaults.Float(_plugin, {name})", BODY)
            self.assertNotIn(f"RegisterFloat({name})", BODY)
        self.assertIn('new JSONStorableFloat("Move forward / back (m)", 0f, (float v) => OnBodyMove(), -5f, 5f);', BODY)
        self.assertIn('new JSONStorableFloat("Turn (degrees)", 0f, (float v) => OnBodyMove(), -180f, 180f);', BODY)

    def test_help_in_the_left_field(self):
        self.assertIn("BodyControlHelp + \"\\n\" + BodyPositionHelp", BODY)


class MoveTests(unittest.TestCase):
    """Version 54 (Don 23:28): absolute offsets from a home placement, one rigid Relocate per change (test_v54_items)."""

    def test_sliders_go_to_home_plus_offsets(self):
        move = method_body(BODY, "private void OnBodyMove()")
        for part in ("if (_syncingMove", "_homePos = _atom.mainController.transform.position", "BodyMover.TargetPosition(_homePos, _homeRot",
                     "Quaternion.Euler(0f, _turnJson.val, 0f) * _homeRot", "BodyMover.Relocate(_atom, pos, rot)"):
            self.assertIn(part, move)

    def test_reset_goes_home(self):
        reset = method_body(BODY, "private void ResetBodyPosition()")
        self.assertIn("BodyMover.Relocate(_atom, _homePos, _homeRot)", reset)
        self.assertIn("_syncingMove = true", reset)
        self.assertIn("finally", reset)

    def test_mover_uses_the_audited_controller_calls(self):
        mover = POSE[POSE.index("public static class BodyMover"):]
        for part in ("atom.freeControllers", "atom.mainController", "main.transform.position = wantPos", ".transform.rotation",
                     "Quaternion.Euler(0f, degrees, 0f)", "Vector3.Cross(Vector3.up, f)", "Quaternion.Inverse("):
            self.assertIn(part, mover)
        for banned in ("GetComponent", "Reflection", "foreach"):
            self.assertNotIn(banned, mover)
