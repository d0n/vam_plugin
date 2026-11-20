"""Version 30: token field masking by focus (first 4 / last 4 visible, no change while the field is focused) and the
one-line first-run note about the xAI token. Checked on the C# sources (the plugin cannot run outside VaM)."""
import json
import re
import unittest
from pathlib import Path

from aibody_companion import settings_file
from tests.test_plugin_menu import method_body, source

ROOT = Path(__file__).resolve().parents[2]


def mask(token: str) -> str:
    """Python twin of AppLink.MaskToken (the C# is checked against this formula below)."""
    t = token.strip()
    if not t:
        return ""
    if len(t) < 12:
        return "****"
    return t[:4] + "****...****" + t[-4:]


class MaskTests(unittest.TestCase):
    def setUp(self):
        self.link = source("AppLink.cs")

    def test_mask_formula_in_the_source(self):
        body = method_body(self.link, "public static string MaskToken(string token)")
        self.assertIn('return t.Substring(0, 4) + "****...****" + t.Substring(t.Length - 4);', body)
        self.assertIn('if (t.Length < 12) return "****";', body)

    def test_examples(self):
        self.assertEqual(mask("xai-dummyvalue-not-real-abcd"), "xai-****...****abcd")
        self.assertEqual(mask("dummy-config-token-0001-not-a-key"), "dumm****...****-key")
        self.assertEqual(mask("short"), "****")
        self.assertEqual(mask(""), "")
        self.assertEqual(len(mask("x" * 20)), len(mask("x" * 200)), "the length of the token is not visible")
        self.assertIn("****", mask("xai-dummyvalue-not-real-abcd"), "still recognised as a mask and ignored as input")

    def test_nothing_changes_while_the_field_is_focused(self):
        show = method_body(self.link, "private void ShowTokenMask()")
        self.assertLess(show.index("TokenFieldFocused()"), show.index("_xaiTokenJson.val = shown"))
        tick = method_body(self.link, "private void TickTokenMask()")
        self.assertIn("if (TokenFieldFocused())", tick)
        self.assertLess(tick.index("return;"), tick.index("ShowTokenMask()"))
        self.assertIn("_tokenInput.isFocused", method_body(self.link, "private bool TokenFieldFocused()"))

    def test_the_old_timer_is_gone_and_focus_is_polled_every_frame(self):
        self.assertNotIn("TokenMaskDelay", self.link)
        self.assertNotIn("_tokenMaskTimer", self.link)
        self.assertIn("TickTokenMask();", method_body(self.link, "public void Update(float dt)"))

    def test_the_input_field_is_kept_and_renewed_on_every_tab_build(self):
        build = method_body(self.link, "public void BuildConnectionSection(UiPage page)")
        self.assertIn("_tokenInput = page.TextInputField(_xaiTokenJson);", build)
        ui = source("UiHelper.cs")
        self.assertIn("public static InputField MakeEditable(", ui)
        self.assertIn("public InputField TextInputField(JSONStorableString p)", ui)

    def test_text_with_the_mask_in_it_is_ignored_and_never_replaces_the_token(self):
        edited = method_body(self.link, "private void OnTokenEdited(string v)")
        masked = edited[edited.index("IsMaskedToken(typed)"):edited.index("if (!_tokenReady)")]
        self.assertIn("return;", masked)
        self.assertNotIn("_xaiToken =", masked)

    def test_config_json_keeps_the_full_token_and_the_scene_only_the_mask(self):
        ai = method_body(self.link, "private JSONClass BuildAiJson(bool forFile)")
        self.assertIn('xai["api_key"] = _xaiToken;', ai)
        self.assertIn("forFile && _tokenReady", ai)
        show = method_body(self.link, "private void ShowTokenMask()")
        self.assertIn("MaskToken(_xaiToken)", show)
        self.assertNotRegex(show, r"_xaiTokenJson\.val = _xaiToken")
        # the first-run note's field is never registered with VaM, so it is never part of a scene
        self.assertNotIn("RegisterString(_hintTokenJson)", self.link)
        self.assertNotIn("RegisterString(_xaiTokenJson)", self.link, "version 31: no scene ever holds the token, not even raw text while typing")

    def test_the_new_unity_ui_member_is_audited_and_stubbed(self):
        audit = (ROOT / "docs" / "API_AUDIT.md").read_text(encoding="utf-8")
        self.assertIn("InputField.isFocused", audit)
        stubs = (ROOT / "tools" / "stubs" / "UnityStubs.cs").read_text(encoding="utf-8")
        self.assertIn("public bool isFocused", stubs)

    def test_the_caret_fix_is_not_implemented(self):
        text = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "AIBody").glob("*.cs"))
        for word in ("customCaretColor", "caretWidth", "SetAsLastSibling"):
            self.assertNotIn(word, text)


class FirstRunHintTests(unittest.TestCase):
    def setUp(self):
        self.link = source("AppLink.cs")

    def test_text_and_labels(self):
        self.assertIn('HintText = "<b>First start: XAI API Token</b>"', self.link)
        self.assertIn('HintClose = "Close"', self.link)
        self.assertIn('HintOk = "OK"', self.link)

    def test_one_line_one_field_one_button_at_the_top_of_every_tab(self):
        build = method_body(self.link, "public void BuildFirstRunHint(UiPage page)")
        self.assertEqual(build.count("page.Header("), 1)
        self.assertEqual(build.count("page.TextInputField("), 1)
        self.assertEqual(build.count("page.ButtonRef("), 1)
        show = method_body(source("AIBody.cs"), "private void ShowTab(int index)")
        self.assertLess(show.index("BuildFirstRunHint(_page)"), show.index("switch (index)"))

    def test_when_it_shows(self):
        visible = method_body(self.link, "public bool FirstRunHintVisible")
        for need in ("_hintDismissed", "_tokenReady", "_xaiToken.Length > 0", "_xaiKeyFileJson", 'KeyConfigured("xai")'):
            self.assertIn(need, visible)

    def test_button_label_follows_the_field_and_ok_saves_like_the_token_field(self):
        edited = method_body(self.link, "private void OnHintEdited(string v)")
        self.assertIn("HintOk : HintClose", edited)
        self.assertIn("IsMaskedToken(typed)", edited)
        button = method_body(self.link, "private void OnHintButton()")
        self.assertIn("_xaiTokenJson.val = typed;", button)
        self.assertIn("_hintDismissed = true;", button)
        self.assertIn("MarkConfigDirty();", button)
        self.assertIn("OnHintChanged()", button)

    def test_the_field_follows_the_masking_rules(self):
        tick = method_body(self.link, "private void TickHint()")
        self.assertIn("_hintInput.isFocused", tick)
        self.assertIn("MaskToken(_hintTyped)", tick)

    def test_dismissal_is_persisted_in_config_json_and_read_back(self):
        self.assertIn('ui["first_run_hint_dismissed"].AsBool = _hintDismissed;', self.link)
        self.assertIn('Protocol.GetBool(uiState, "first_run_hint_dismissed", false)', self.link)
        self.assertEqual(settings_file.defaults()["ui"], {"first_run_hint_dismissed": False, "background_setup_applied": 0})
        self.assertIn("ui", settings_file.PLUGIN_CATEGORIES)
        schema = json.loads((ROOT / "protocol/schema/config.schema.json").read_text(encoding="utf-8"))
        self.assertIn("first_run_hint_dismissed", schema["properties"]["ui"]["properties"])
        data, errors = settings_file.validate({"ui": {"first_run_hint_dismissed": "true"}})
        self.assertEqual(errors, [])
        self.assertTrue(data["ui"]["first_run_hint_dismissed"])

    def test_button_label_change_uses_an_audited_member(self):
        audit = (ROOT / "docs" / "API_AUDIT.md").read_text(encoding="utf-8")
        self.assertIn("buttonText.text", audit)


if __name__ == "__main__":
    unittest.main()
