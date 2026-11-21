"""Character configuration wizard (after version 37, Leon): gate, skip path, each step.

The wizard lives in the plugin UI (tab AI Character, section Characters), not in the companion
console setup. The steps only record settings; they do not change a Person in VaM.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from aibody_companion.characters import context_text, normalize, normalize_gender
from aibody_companion.pipeline.engines import EngineSet
from aibody_companion.settings_file import CHOICES, DEFAULTS, PLUGIN_CATEGORIES, validate

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


class GateTests(unittest.TestCase):
    def setUp(self):
        self.cs = source("CharacterWizard.cs")
        self.build = method_body(self.cs, "public void Build(UiPage page)")

    def test_gate_question_is_english_and_exact(self):
        self.assertIn('GateQuestion = "Do you want to configure your characters?"', self.cs)
        self.assertIn("GateQuestion", method_body(self.cs, "public string InfoText()"))
        # UI language is English; the German wording is not used in the plugin.
        self.assertNotIn("Willst du deine Charaktere konfigurieren", self.cs)

    def test_gate_shows_yes_and_no_until_answered(self):
        # Unanswered: only the Yes / No buttons, no gender popups yet.
        unanswered = method_body(self.build, "if (_askedJson == null || !_askedJson.val)")
        self.assertIn('page.Button("Yes", OnYes)', unanswered)
        self.assertIn('page.Button("No", OnNo)', unanswered)
        self.assertNotIn("page.Popup", unanswered)
        self.assertIn("return;", unanswered)

    def test_yes_opens_the_steps(self):
        yes = method_body(self.cs, "private void OnYes()")
        self.assertIn("_askedJson.val = true;", yes)
        self.assertIn("_wantedJson.val = true;", yes)
        self.assertIn("Rebuild()", yes)


class SkipPathTests(unittest.TestCase):
    def setUp(self):
        self.cs = source("CharacterWizard.cs")
        self.build = method_body(self.cs, "public void Build(UiPage page)")

    def test_no_hides_the_steps_and_does_not_keep_asking(self):
        no = method_body(self.cs, "private void OnNo()")
        self.assertIn("_askedJson.val = true;", no)
        self.assertIn("_wantedJson.val = false;", no)
        skipped = method_body(self.build, "if (!_wantedJson.val)")
        self.assertIn('page.Button("Configure characters", OnReopen)', skipped)
        self.assertNotIn("page.Popup", skipped)
        self.assertNotIn('page.Button("Yes"', skipped)
        # After No the gender steps are not in the skip branch; they only follow when wanted.
        self.assertLess(self.build.index("if (!_wantedJson.val)"), self.build.index("page.Popup(_aiGenderJson)"))
        self.assertIn("return;", skipped)

    def test_configure_characters_reopens_the_gate(self):
        reopen = method_body(self.cs, "private void OnReopen()")
        self.assertIn("_askedJson.val = false;", reopen)
        self.assertNotIn("_wantedJson.val = true;", reopen)
        info = method_body(self.cs, "public string InfoText()")
        self.assertIn("<b>Configure characters</b>", info)
        self.assertIn("<b>No</b> skips this setup and does not ask again", info)

    def test_not_in_companion_console_setup(self):
        setup = (ROOT / "companion" / "aibody_companion" / "setup.py").read_text(encoding="utf-8")
        self.assertNotIn("Do you want to configure your characters?", setup)
        self.assertNotIn("AI gender/body", setup)
        self.assertNotIn("Your character gender", setup)
        # The console wizard stays the two independent first-start points.
        self.assertIn('QUESTION_BACKGROUND = "Do you want a greenscreen background?"', setup)
        self.assertIn('QUESTION_CHOICE = "Choose what to use"', setup)


class StepTests(unittest.TestCase):
    def setUp(self):
        self.cs = source("CharacterWizard.cs")
        self.build = method_body(self.cs, "public void Build(UiPage page)")
        self.info = method_body(self.cs, "public string InfoText()")
        self.create = method_body(self.cs, "public void CreateStorables()")

    def test_step1_ai_gender_body_female_or_male_only(self):
        self.assertIn('AiGenderLabel = "AI gender/body"', self.cs)
        self.assertIn('new JSONStorableStringChooser(AiGenderLabel', self.create)
        self.assertIn("genders.Add(Female);", self.create)
        self.assertIn("genders.Add(Male);", self.create)
        self.assertIn('Female = "Female"', self.cs)
        self.assertIn('Male = "Male"', self.cs)
        self.assertIn("page.Popup(_aiGenderJson);", self.build)
        # Nothing is applied to DAZCharacterSelector / geometry; the choice is recorded.
        self.assertNotIn("DAZCharacterSelector", self.cs)
        self.assertNotIn("selectedCharacter", self.cs)
        self.assertNotIn("SetGender", self.cs)
        self.assertIn("they do not change the Person's body in VaM", self.info)
        self.assertIn("<b>AI gender/body</b> records", self.info)

    def test_step2_user_character_gender(self):
        self.assertIn('UserGenderLabel = "Your character gender"', self.cs)
        self.assertIn("page.Popup(_userGenderJson);", self.build)
        self.assertIn("<b>Your character gender</b> records", self.info)
        # Single-character rule: the wizard does not drive a second Person.
        self.assertIn("AIBody still drives only this Person", self.cs)
        self.assertNotIn("GetAtoms()", self.cs)
        self.assertNotIn("containingAtom", self.cs)

    def test_step3_clothing_is_free_choice_with_no_predefined_ids(self):
        self.assertIn('ClothingHeader = "Clothing"', self.cs)
        self.assertIn('page.Header("<b>Clothing</b>")', self.build)
        self.assertIn("use VaM's own Clothing tab", self.info)
        self.assertIn("<b>Clothing</b> is a free choice with nothing predefined", self.info)
        self.assertIn("AIBody has no clothing list and does not change what anyone wears", self.info)
        # No invented clothing ids, catalogs or Clothing tab API.
        for banned in ("ClothingChooser", "clothingItems", "DAZClothing", "GetClothing",
                       "builtin clothing", "Female Casual", "Male Casual", "Underwear"):
            self.assertNotIn(banned, self.cs)
        # The Clothing header has no controls under it in Build (it is the last thing in the wanted path).
        wanted_tail = self.build[self.build.index('page.Header("<b>Clothing</b>")'):]
        self.assertNotIn("page.Popup", wanted_tail)
        self.assertNotIn("page.Button", wanted_tail)
        self.assertNotIn("page.Toggle", wanted_tail)

    def test_answers_are_registered_and_written_with_the_scene_and_config(self):
        self.assertIn("RegisterBool(_askedJson)", self.create)
        self.assertIn("RegisterBool(_wantedJson)", self.create)
        self.assertIn("RegisterStringChooser(_aiGenderJson)", self.create)
        self.assertIn("RegisterStringChooser(_userGenderJson)", self.create)
        write = method_body(self.cs, "public void WriteSettings(JSONClass root)")
        self.assertIn('characters["setup_answered"]', write)
        self.assertIn('characters["setup_wanted"]', write)
        self.assertIn('characters["ai_gender"]', write)
        self.assertIn('characters["user_gender"]', write)
        self.assertIn('root["characters"] = characters', write)
        body = source("Body.cs")
        self.assertIn("Characters.WriteSettings(root)", method_body(body, "public void WriteSettings(JSONClass root)"))
        self.assertIn("Characters.ApplySettings(root)", method_body(body, "public void ApplySettings(JSONClass root)"))
        self.assertIn("Characters.Build(page)", method_body(body, "public void BuildCharacterTab(UiPage page)"))
        # Characters is the first topic, before Body control.
        tab = method_body(body, "public void BuildCharacterTab(UiPage page)")
        self.assertLess(tab.index("Characters.Build(page)"), tab.index('"<b>Body control</b>"'))


class IntegrationAndSandboxTests(unittest.TestCase):
    def test_cslist_includes_the_new_file_before_body(self):
        names = [ln.strip() for ln in (SRC / "AIBody.cslist").read_text().splitlines() if ln.strip()]
        self.assertIn("CharacterWizard.cs", names)
        self.assertLess(names.index("CharacterWizard.cs"), names.index("Body.cs"))
        self.assertEqual(names.count("CharacterWizard.cs"), 1)

    def test_no_reflection_or_indexers_in_the_wizard(self):
        cs = source("CharacterWizard.cs")
        self.assertNotIn("System.Reflection", cs)
        self.assertNotIn("this[", cs)
        self.assertNotIn("UnityEngine.Networking", cs)
        self.assertNotIn("UnityWebRequest", cs)
        # foreach over a list of known genders is fine; no dictionary Keys/Values.
        self.assertNotIn(".Keys", cs)
        self.assertNotIn(".Values", cs)

    def test_info_prose_uses_bold_control_labels(self):
        info = method_body(source("CharacterWizard.cs"), "public string InfoText()")
        for label in ("Yes", "No", "Configure characters", "AI gender/body", "Your character gender", "Clothing"):
            self.assertIn(f"<b>{label}</b>", info)

    def test_left_info_is_wired_into_the_ai_character_tab(self):
        info = method_body(source("Body.cs"), "public string CharacterInfoText()")
        self.assertIn("Characters.InfoText()", info)
        self.assertLess(info.index("Characters.InfoText()"), info.index("Poses:"))


class CompanionContextTests(unittest.TestCase):
    def test_normalize_and_gender(self):
        self.assertEqual(normalize_gender("Female"), "Female")
        self.assertEqual(normalize_gender("Male"), "Male")
        self.assertEqual(normalize_gender("female"), "")
        self.assertEqual(normalize_gender("Other"), "")
        self.assertEqual(normalize_gender(None), "")
        data = normalize({"setup_answered": "true", "setup_wanted": True, "ai_gender": "Female",
                          "user_gender": "nope", "extra": 1})
        self.assertEqual(data, {"setup_answered": True, "setup_wanted": True,
                                "ai_gender": "Female", "user_gender": ""})

    def test_context_text_empty_and_set(self):
        self.assertEqual(context_text("", ""), "")
        self.assertEqual(context_text("Female", ""), "The AI character's body is female.")
        self.assertEqual(context_text("", "Male"), "The user's character is male.")
        self.assertEqual(context_text("Female", "Male"),
                         "The AI character's body is female. The user's character is male.")
        self.assertEqual(context_text("futa", "unknown"), "")

    def test_persona_text_includes_character_context(self):
        engines = EngineSet({"persona": "You are Anna."})
        self.assertNotIn("AI character's body", engines.persona_text())
        engines.characters = normalize({"ai_gender": "Female", "user_gender": "Male"})
        text = engines.persona_text()
        self.assertIn("You are Anna.", text)
        self.assertIn("The AI character's body is female.", text)
        self.assertIn("The user's character is male.", text)

    def test_settings_defaults_and_validation(self):
        self.assertEqual(DEFAULTS["characters"], {
            "setup_answered": False, "setup_wanted": False, "ai_gender": "", "user_gender": "",
        })
        self.assertIn("characters", PLUGIN_CATEGORIES)
        self.assertEqual(CHOICES[("characters", "ai_gender")], ("", "Female", "Male"))
        data, errors = validate({"version": 1, "written_by": "test",
                                 "characters": {"setup_answered": True, "setup_wanted": True,
                                                "ai_gender": "Female", "user_gender": "Male"}})
        self.assertEqual(errors, [])
        self.assertEqual(data["characters"]["ai_gender"], "Female")
        _, bad = validate({"version": 1, "written_by": "test",
                           "characters": {"ai_gender": "Futa", "user_gender": "Male"}})
        self.assertTrue(any("ai_gender" in e for e in bad))


if __name__ == "__main__":
    unittest.main()
