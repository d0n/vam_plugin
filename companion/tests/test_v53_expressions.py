"""Version 53 (Don, 22.11.2026 20:49 / 20:57): expressions not working / not visible, the 'Show expression' button, and
the button regrouping. Not the same root cause as the poses (v52), but the same pattern on the face: VaM's own Auto
Expressions animate the face morphs every frame and covered AIBody's expression; and the Expression menu started on
'neutral' (an empty preset), so 'Show expression' showed nothing."""
from __future__ import annotations

import unittest

from .test_plugin_menu import method_body, source


class ExpressionTests(unittest.TestCase):
    def setUp(self):
        self.ec = source("ExpressionController.cs")
        self.body = source("Body.cs")

    def test_menu_never_starts_on_an_expression_that_shows_nothing(self):
        names = method_body(self.ec, "public IEnumerable<string> PresetNames")
        self.assertIn('{ "happy", "smile", "sad", "angry", "surprised", "thinking" }', self.ec)
        self.assertIn('new[] { "listening", "neutral" }', names)
        self.assertNotIn("_presets.Keys", names)
        # version 66: the Expression menu is gone; PresetNames still feeds the AI's expression list (state / heartbeat)
        self.assertIn("_expressions.PresetNames", self.body)

    def test_manual_show_expression_is_gone_but_the_morph_report_stays(self):
        # version 66: ShowChosenExpression and the menu are removed; the expression code the AI uses is unchanged
        self.assertNotIn("ShowChosenExpression", self.body)
        self.assertNotIn("_expressionChoiceJson", self.body)
        self.assertIn('morphs found', method_body(self.ec, "public bool SetExpression(string name, float intensity, float blendTime, float hold)"))

    def test_two_sided_names_fall_back_to_left_and_right(self):
        apply = method_body(self.ec, "private List<string> ApplyTargets(")
        self.assertIn('_layer.SetTarget(kv.Key + " Left"', apply)
        self.assertIn('_layer.SetTarget(kv.Key + " Right"', apply)
        self.assertIn("if (!left && !right) missing.Add(kv.Key);", apply)

    def test_vam_auto_expressions_pause_while_an_expression_shows(self):
        self.assertIn("_expressions.OnShowingChanged = PauseAutoExpressions;", self.body)
        pause = method_body(self.body, "private void PauseAutoExpressions(bool showing)")
        self.assertIn('GetStorableByID("AutoExpressions")', pause)
        self.assertIn('GetBoolJSONParam("enabled")', pause)
        self.assertIn("_autoWasOn = enabled.val;", pause)
        self.assertIn("if (_autoWasOn) { enabled.val = true;", pause, "put back only if it was on")
        for sig in ("public void Reset(float blendTime)", "public void RestoreNow()"):
            self.assertIn("SetShowing(false);", method_body(self.ec, sig), sig)
        self.assertIn("SetShowing(preset.Count > missing.Count);", self.ec)


class ButtonRegroupingTests(unittest.TestCase):
    def test_buttons(self):
        # version 66: Show expression / Reset expression are gone from the tab (test_version66); reloading stays
        tab = method_body(source("Body.cs"), "public void BuildCharacterTab(UiPage page)")
        self.assertNotIn('page.Button("Show expression"', tab)
        self.assertNotIn('page.Button("Reset expression"', tab)
        self.assertNotIn('page.Button("Reload expressions (expressions.json)"', tab)
        body = source("Body.cs")
        self.assertIn('_plugin.RegisterAction(new JSONStorableAction("Reload config files", ReloadConfigFiles));', body)
        self.assertIn("ReloadExpressions();", method_body(body, "public void ReloadConfigFiles()"))
        reload = method_body(source("AIBody.cs"), "private void ReloadConfigJson()")
        self.assertIn("_body.ReloadConfigFiles();", reload)
        self.assertNotIn("expressions.json reloaded: ", reload)

    def test_no_expression_help_in_the_left_field(self):
        body = source("Body.cs")
        self.assertNotIn("ExpressionHelp", body)
        self.assertNotIn("ExpressionsNote", body)


if __name__ == "__main__":
    unittest.main()
