"""Version 24: the xAI token is stored in config.json (ai.xai.api_key, plain text, Leon's explicit decision) and
filled into the plugin field on start; shown masked; a security notice sits in the plugin's big info field and in
config.json (ai.xai.api_key_warning). Only dummy values, none of them looks like a real key."""
from __future__ import annotations

import io
import json
import logging
import re
import tempfile
import unittest
from pathlib import Path

from aibody_companion import logsetup, settings_file
from aibody_companion.config import Config
from aibody_companion.pipeline.engines import EngineSet
from tests.test_plugin_menu import method_body, source

TOKEN = "dummy-config-token-0001-not-a-key"
FIELD = "dummy-field-token-0002-not-a-key"
ENV = "dummy-env-token-0003-not-a-key"
FILE_KEY = "dummy-file-token-0004-not-a-key"


def engines(api_key="", env=None, key_file=""):
    return EngineSet({"xai": {"api_key": api_key, "key_file": key_file}}, env=env or {})


class ConfigJsonTests(unittest.TestCase):
    def test_defaults_have_the_key_and_the_warning_next_to_it(self):
        xai = settings_file.defaults()["ai"]["xai"]
        self.assertEqual(xai["api_key"], "")
        self.assertEqual(xai["api_key_warning"], settings_file.KEY_WARNING_TEXT)
        self.assertTrue(xai["api_key_warning"].startswith("SECURITY NOTICE"))
        keys = list(xai)
        self.assertEqual(keys[keys.index("api_key") + 1], "api_key_warning")

    def test_warning_text_is_the_same_in_the_plugin_and_in_config_json(self):
        link = source("AppLink.cs")
        m = re.search(r'public const string XaiTokenWarning = (.*?");\s*\n', link, re.S)
        literal = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)))
        # the left info field shows the label in bold (Leon's style rule, 20.11.2026); config.json holds plain text
        self.assertEqual(re.sub(r"</?b>", "", literal), settings_file.KEY_WARNING_TEXT)
        m = re.search(r'public const string XaiTokenWarningPlain = (.*?");\s*\n', link, re.S)
        plain = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)))
        self.assertEqual(plain, settings_file.KEY_WARNING_TEXT)
        self.assertIn('xai["api_key_warning"] = XaiTokenWarningPlain;', link)

    def test_validate_accepts_both_keys_and_load_keeps_them(self):
        data, errors = settings_file.validate({"ai": {"xai": {"api_key": TOKEN, "api_key_warning": "mine"}}})
        self.assertEqual(errors, [])
        self.assertEqual((data["ai"]["xai"]["api_key"], data["ai"]["xai"]["api_key_warning"]), (TOKEN, "mine"))
        _, errors = settings_file.validate({"ai": {"xai": {"api_key": {"x": TOKEN}}}})
        self.assertTrue(errors and TOKEN not in " ".join(errors))

    def test_old_file_gets_the_new_keys_and_a_stored_token_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            old = settings_file.defaults()
            del old["ai"]["xai"]["api_key"], old["ai"]["xai"]["api_key_warning"]
            path.write_text(json.dumps(old), encoding="utf-8")
            added = settings_file.add_missing_companion_sections(path)
            self.assertIn("ai.xai.api_key", added)
            self.assertIn("ai.xai.api_key_warning", added)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["ai"]["xai"]["api_key"] = TOKEN
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(settings_file.add_missing_companion_sections(path), [])
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["ai"]["xai"]["api_key"], TOKEN)

    def test_the_app_never_writes_a_token_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = settings_file.settings_path(tmp)
            settings_file.write_defaults_if_missing(path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["ai"]["xai"]["api_key"], "")

    def test_loading_config_json_registers_the_token_as_a_secret_and_never_logs_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = settings_file.settings_path(tmp)
            settings_file.write_defaults_if_missing(path)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["ai"]["xai"]["api_key"] = TOKEN
            path.write_text(json.dumps(data), encoding="utf-8")
            stream = io.StringIO()
            handler = logging.StreamHandler(stream)
            handler.setFormatter(logsetup.RedactingFormatter("%(message)s"))
            logging.getLogger().addHandler(handler)
            try:
                cfg = Config(vam_root=tmp)
                settings_file.apply_to_config(cfg)
                logging.getLogger("x").info("token is %s", TOKEN)
            finally:
                logging.getLogger().removeHandler(handler)
            self.assertEqual(cfg.ai["xai"]["api_key"], TOKEN)
            self.assertNotIn(TOKEN, stream.getvalue(), "the loaded token is registered as a secret before anything is logged")
            self.assertNotIn(TOKEN, logsetup.redact(f"token is {TOKEN}"))
            self.assertNotIn(TOKEN, settings_file.KEY_HINT_TEXT)


class PrecedenceTests(unittest.TestCase):
    def test_config_key_is_used_without_any_other_source(self):
        e = engines(api_key=TOKEN)
        self.assertEqual(e.key("xai"), TOKEN)
        info = e.key_info()["xai"]
        self.assertEqual(info["state"], "configured")
        self.assertEqual(info["detail"], "config.json ai.xai.api_key")
        self.assertNotIn(TOKEN, json.dumps(e.key_info()))
        self.assertNotIn(TOKEN, json.dumps(e.status()))

    def test_order_field_then_config_then_environment_then_key_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            kf = Path(tmp) / "k.txt"
            kf.write_text(FILE_KEY, encoding="utf-8")
            e = engines(api_key=TOKEN, env={"XAI_API_KEY": ENV}, key_file=str(kf))
            self.assertEqual(e.key("xai"), TOKEN)  # config beats environment and key file
            e.set_ui_key("xai", FIELD)
            self.assertEqual(e.key("xai"), FIELD)  # the live field beats config
            e.set_ui_key("xai", "")
            self.assertEqual(e.ai["xai"]["api_key"], "", "emptying the field forgets the stored key (the plugin clears it in the file too)")
            self.assertEqual(e.key("xai"), ENV)  # then environment ...
            e2 = engines(env={}, key_file=str(kf))
            self.assertEqual(e2.key("xai"), FILE_KEY)  # ... then the key file
            self.assertIsNone(engines().key("xai"))

    def test_same_token_from_the_field_is_no_change(self):
        e = engines(api_key=TOKEN)
        e.set_ui_key("xai", TOKEN)
        self.assertEqual(e.key("xai"), TOKEN)
        self.assertEqual(e.key_info()["xai"]["detail"], "plugin field 'XAI API Token'")

    def test_an_empty_first_event_does_not_drop_the_stored_key(self):
        e = engines(api_key=TOKEN)
        self.assertFalse(e.set_ui_key("xai", ""))  # plugin sends "" before it has read config.json
        self.assertEqual(e.key("xai"), TOKEN)


class PluginSourceTests(unittest.TestCase):
    def setUp(self):
        self.link = source("AppLink.cs")
        self.plugin = source("AIBody.cs")

    def test_start_reads_the_token_from_config_json_only_after_a_successful_read(self):
        update = method_body(self.plugin, "private void UpdateSettings(float dt)")
        self.assertIn("readOk = true", update)
        self.assertIn("if (readOk)", update)
        self.assertIn("_link.AdoptToken(file)", update)
        self.assertLess(update.index("_link.AdoptToken(file)"), update.index("_settingsInitJson.val = true"))
        reload = method_body(self.plugin, "private void ReloadConfigJson()")
        self.assertIn("_link.AdoptToken(file)", reload)

    def test_adopt_token_fills_the_field_with_the_mask_not_the_token(self):
        adopt = method_body(self.link, "public void AdoptToken(JSONClass root)")
        self.assertIn('Protocol.GetString(xai, "api_key", "")', adopt)
        self.assertIn("_tokenReady = true", adopt)
        self.assertIn("ShowTokenMask()", adopt)
        show = method_body(self.link, "private void ShowTokenMask()")
        self.assertIn("MaskToken(_xaiToken)", show)
        self.assertNotRegex(show, r"_xaiTokenJson\.val = _xaiToken")

    def test_mask_never_overwrites_the_token(self):
        edited = method_body(self.link, "private void OnTokenEdited(string v)")
        self.assertLess(edited.index("IsMaskedToken(typed)"), edited.index("_xaiToken = typed"))
        masked_branch = edited[edited.index("IsMaskedToken(typed)"):edited.index("if (!_tokenReady)")]
        self.assertIn("return;", masked_branch)
        self.assertNotIn("_xaiToken =", masked_branch)
        self.assertIn("if (_settingTokenDisplay) return;", edited)
        mask = method_body(self.link, "public static string MaskToken(string token)")
        self.assertIn("Substring(0, 4)", mask, "first 4 characters stay visible")
        self.assertIn("Substring(t.Length - 4)", mask)
        self.assertIn("TickTokenMask();", method_body(self.link, "public void Update(float dt)"))

    def test_nothing_is_written_or_cleared_before_config_json_was_read(self):
        ai = method_body(self.link, "private JSONClass BuildAiJson(bool forFile)")
        self.assertIn("forFile && _tokenReady", ai)
        edited = method_body(self.link, "private void OnTokenEdited(string v)")
        not_ready = edited[edited.index("if (!_tokenReady)"):edited.index("_xaiToken = typed;")]
        self.assertIn("typed.Length > 0", not_ready)  # an early empty text does not clear anything

    def test_security_notice_is_in_the_big_info_field_not_under_the_token_field(self):
        info = method_body(self.link, "public string VoiceInfoText()")
        self.assertIn("XaiTokenWarning", info)
        self.assertTrue(info.index("XaiTokenWarning") < info.index("_modeHelpJson"))
        voice = method_body(self.link, "public void BuildConnectionSection(UiPage page)")
        self.assertNotIn("XaiTokenWarning", voice)
        self.assertTrue(settings_file.KEY_WARNING_TEXT.startswith("SECURITY NOTICE: "))
        self.assertIn("publish", settings_file.KEY_WARNING_TEXT)
        self.assertIn("config.json", settings_file.KEY_WARNING_TEXT)

    def test_no_new_api_and_no_logging_of_the_token(self):
        for name in ("AIBody.cs", "AppLink.cs"):
            for line in source(name).splitlines():
                if re.search(r"Log\.(Info|Debug|Error|Warn)\(", line):
                    self.assertNotRegex(line, r"_xaiToken\b|_xaiTokenJson|XaiToken\b(?!Label|Hint|Warning)", f"{name}: {line.strip()}")
        for banned in ("contentType", "asteriskChar", "Thread.Sleep", "UnityWebRequest"):
            self.assertNotIn(banned, self.link)
        self.assertNotRegex(self.link, r"foreach\s*\([^)]*\.(Keys|Values)\)")


if __name__ == "__main__":
    unittest.main()
