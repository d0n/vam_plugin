"""Version 65 (26.11.2026, on top of v64): choosers with fewer than two entries are a read-only line, not a dropdown;
a saved "0" or empty value is ignored and the default stays. Version everywhere and English release notes."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__
from aibody_companion import setup as first_start

from .test_plugin_menu import method_body, source

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class VersionTests(TestCase):
    def test_version_65_is_historical(self):
        """Historical: version 65 sources are gone after the v66 bump; consistency is test_version66."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version66.py").is_file())
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 65, release; on top of v64)", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## T121", proto)
        self.assertIn("a saved `\"0\"` or empty value", (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8"))


class OneEntryChooserTests(TestCase):
    def test_popup_methods_switch_on_count(self):
        ui = src("UiHelper.cs")
        popup = method_body(ui, "public void Popup(JSONStorableStringChooser p)")
        scroll = method_body(ui, "public void ScrollablePopup(JSONStorableStringChooser p)")
        self.assertIn("Chooser(p, false);", popup)
        self.assertIn("Chooser(p, true);", scroll)
        chooser = method_body(ui, "private void Chooser(JSONStorableStringChooser p, bool scrollable)")
        self.assertIn("if (UiChooser.ShowsDropdown(p))", chooser)
        self.assertIn("CreateScrollablePopup(p, _right)", chooser)
        self.assertIn("CreatePopup(p, _right)", chooser)
        self.assertIn("UiChooser.Line(p)", chooser)
        self.assertIn("CreateTextField", ui[ui.index("public static UIDynamicTextField Header"):ui.index("public static class UiChooser")])

    def test_placeholder_and_line_rules(self):
        ui = src("UiHelper.cs")
        self.assertIn("public const int DropdownMin = 2;", ui)
        is_ph = method_body(ui, "public static bool IsPlaceholder(string value)")
        self.assertIn('return string.IsNullOrEmpty(value) || value == "0";', is_ph)
        self.assertNotIn('"None"', is_ph)
        self.assertNotIn('"Not set"', is_ph)
        self.assertNotIn('"null"', is_ph)
        self.assertNotIn('"Off"', is_ph)
        line = method_body(ui, "public static string Line(JSONStorableStringChooser p)")
        self.assertIn('"<b>" + name + "</b>: (none)"', line)
        self.assertIn('"<b>" + name + "</b>: " + value', line)
        apply = method_body(ui, "public static void ApplyValue(JSONStorableStringChooser chooser, string value)")
        self.assertIn("if (chooser == null || IsPlaceholder(value)) return;", apply)

    def test_call_sites_unchanged_so_storables_stay(self):
        """The menus are still the same JSONStorableStringChooser objects; only how they are drawn changes."""
        body = src("Body.cs")
        self.assertIn("page.ScrollablePopup(_idlePoseDefaultJson);", body)
        self.assertIn("page.ScrollablePopup(_poseCommandChoiceJson);", body)
        self.assertIn('new JSONStorableStringChooser("Idle default pose"', body)
        self.assertIn('new JSONStorableStringChooser("Pose command"', body)
        link = src("AppLink.cs")
        self.assertIn("page.Popup(_aiModeJson);", link)
        self.assertIn("page.Popup(_llmJson);", link)
        self.assertIn("page.Popup(_personaJson);", link)
        self.assertIn("page.ScrollablePopup(_languageJson);", link)
        self.assertIn("page.ScrollablePopup(_voiceJson);", link)
        self.assertIn("page.Popup(_sttJson);", link)
        self.assertIn("page.Popup(_ttsJson);", link)
        self.assertIn("page.Popup(Mode);", src("MicConfig.cs"))
        self.assertIn("page.Popup(VadEngine);", src("MicConfig.cs"))
        wiz = src("CharacterWizard.cs")
        self.assertIn("page.Popup(_aiGenderJson);", wiz)
        self.assertIn("page.Popup(_userGenderJson);", wiz)

    def test_saved_zero_is_not_added_and_falls_back(self):
        body = src("Body.cs")
        self.assertIn("UiChooser.ApplyValue(chooser, value);", method_body(body, "private static void SetChooserValue(JSONStorableStringChooser chooser, string value)"))
        self.assertIn("UiChooser.Sanitize(_idlePoseDefaultJson, IdlePoseScheduler.DefaultIdlePose);", body)
        self.assertIn("UiChooser.DropPlaceholders(commands);", body)
        link = src("AppLink.cs")
        self.assertIn("UiChooser.ApplyValue(_sttJson,", link)
        self.assertIn("UiChooser.ApplyValue(_llmJson,", link)
        self.assertIn("UiChooser.ApplyValue(_ttsJson,", link)
        self.assertIn("if (UiChooser.IsPlaceholder(voice)) return;", method_body(link, "private void SetVoice(string voice)"))
        self.assertIn("if (UiChooser.IsPlaceholder(code)) return;", method_body(link, "private void SetLanguage(string code)"))
        ensure = method_body(link, "public static void EnsureChoices(JSONStorableStringChooser chooser, string[] builtIn)")
        self.assertIn("UiChooser.DropPlaceholders(choices);", ensure)
        self.assertIn("else if (UiChooser.IsPlaceholder(chooser.val) && choices.Count > 0) chooser.val = choices[0];", ensure)

    def test_tab_rebuilds_when_the_count_crosses_two(self):
        refresh = method_body(src("Body.cs"), "public void RefreshCharacterChoices()")
        self.assertIn("if (poseDrop != UiChooser.ShowsDropdown(_poseCommandChoiceJson)", refresh)
        self.assertIn("RebuildTab = true;", refresh)

    def test_meaningful_none_entries_stay(self):
        self.assertIn('public const string NotSet = "Not set";', src("CharacterWizard.cs"))
        self.assertIn('public const string NoThrustTarget = "None";', src("DmThrustController.cs"))
        self.assertIn('"null"', src("AppLink.cs"))  # STT offline test engine
        # persona "(none)" still maps to Anna, and is not a menu entry
        self.assertIn('name == "(none)"', src("AppLink.cs"))
        self.assertIn("PersonaDefault", method_body(src("AppLink.cs"), "private void SetPersona(string name)"))

    def test_dollmaster_and_companion_have_no_forced_one_entry_change(self):
        # Dollmaster keeps its own CreatePopup (world UI); nine personas ship, Thrust Control has None + patterns
        self.assertIn("dm.CreatePopup(thrustAtomChooser);", src("DmThrustController.cs"))
        self.assertIn("personalityChoice.popup = popup;", src("DmPluginState.cs"))
        panel = (ROOT / "companion" / "aibody_companion" / "remote" / "panel.py").read_text(encoding="utf-8")
        self.assertNotIn("<select", panel)
        self.assertIn("function chips(", panel)
