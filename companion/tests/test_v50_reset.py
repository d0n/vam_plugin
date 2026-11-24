"""Version 50 (Don, call 22.11.2026 20:35, tested v49 after a full config reset): the reset path and a fresh config.

1. 'Reset to Default' clears the XAI API Token (plugin field, config.json ai.xai.api_key, the companion's copy); the
   token is never logged.
2. / 5. / 6. The engine menus always list the real engines (xai first), also before the companion app connected, and
   default to xai; before, they were filled only by the companion heartbeat and defaulted to the offline test engines
   null / echo / tone, so a reset or fresh config could only run them (no speech understood without the key override).
3. Persona: no '(none)'; the female starter Anna (default) and the male starter Marc.
4. Memory on by default.
7. Mic enabled and Push-to-talk interrupts speech on by default.
The reset itself is reproduced with FakePlugin: every menu back to the defaults the plugin registers, token emptied.
"""
from __future__ import annotations

import io
import json
import logging
import re
from pathlib import Path
from unittest import TestCase

from aibody_companion import logsetup, settings_file
from aibody_companion.audio.mic_settings import MicSettings
from aibody_companion.config import ENGINES_AVAILABLE
from aibody_companion.personas import STARTER_PERSONAS
from tests.test_xai_token import TOKEN, TokenFlowBase

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


def cs_array(text: str, name: str) -> list[str]:
    m = re.search(r"string\[\] " + name + r" = \{([^}]*)\}", text)
    assert m, name
    return re.findall(r'"([^"]*)"', m.group(1))


def reset_plugin(plugin) -> None:
    """What ConfirmReset does to the menus the companion sees: every saved setting back to its registered default
    (the v50 defaults below), then ClearToken (field empty -> config event keys.xai = "")."""
    plugin.ui["engines"] = {"stt": "xai", "llm": "xai", "tts": "xai"}
    plugin.ui["mic"].update({"enabled": True, "mode": "vad", "ptt_interrupts": True})
    plugin.ai_ui.update({"mode": "qa", "persona_name": "Anna", "language": "de", "memory": {"enabled": True}})
    plugin.set_xai_token("")


class PluginDefaultsTests(TestCase):
    def setUp(self):
        self.link = source("AppLink.cs")
        self.mic = source("MicConfig.cs")

    def test_1_reset_clears_the_token(self):
        confirm = method_body(source("AIBody.cs"), "private void ConfirmReset()")
        self.assertLess(confirm.index("Defaults.ResetAll(this)"), confirm.index("_link.ClearToken()"))
        self.assertIn("The XAI API Token is cleared", confirm)
        clear = method_body(self.link, "public void ClearToken()")
        for part in ('_xaiToken = "";', "ShowTokenMask();", "UpdateKeyStatus();", "MarkConfigDirty();"):
            self.assertIn(part, clear)
        self.assertNotIn("Log.", clear, "the token is never logged")
        # config.json gets "" (BuildAiJson writes the token once the file was read) and the config event keys.xai = ""
        self.assertIn('xai["api_key"] = _xaiToken;', self.link)
        self.assertIn('keys["xai"] = XaiToken;', self.link)
        info = method_body(source("AIBody.cs"), "private string ResetInfo()")
        self.assertIn("also clears your <b>XAI API Token</b>", info)
        self.assertNotIn("never deletes your", info)

    def test_2_5_6_engine_menus_list_the_real_engines_and_default_to_xai(self):
        for kind, name in (("stt", "SttChoices"), ("llm", "LlmChoices"), ("tts", "TtsChoices")):
            choices = cs_array(self.link, name)
            self.assertEqual(sorted(choices), sorted(ENGINES_AVAILABLE[kind]), kind)
            self.assertEqual(choices[0], "xai", f"{kind}: the real engine first")
        self.assertIn('public const string EngineDefault = "xai";', self.link)
        for label, name in (("Speech-to-text", "SttChoices"), ("Language model", "LlmChoices"), ("Text-to-speech", "TtsChoices")):
            self.assertIn(f'Engine("{label}", {name}, EngineDefault)', self.link)
        engine = method_body(self.link, "private JSONStorableStringChooser Engine(")
        self.assertIn("new List<string>(choices)", engine)
        set_choices = method_body(self.link, "private void SetChoices(JSONStorableStringChooser chooser, JSONArray names)")
        self.assertIn("new List<string>(BuiltInChoices(chooser))", set_choices, "the heartbeat never shrinks the list")

    def test_3_persona_menu_has_no_none(self):
        self.assertNotIn("PersonaNone", self.link)
        self.assertIn('public const string PersonaFemale = "Anna";', self.link)
        self.assertIn('public const string PersonaMale = "Marc";', self.link)
        self.assertIn("public static readonly string[] StarterPersonas = { PersonaFemale, PersonaMale };", self.link)
        self.assertIn('new JSONStorableStringChooser("Persona", new List<string>(StarterPersonas), PersonaDefault', self.link)
        self.assertEqual(set(STARTER_PERSONAS), {"Anna", "Marc"})
        refresh = method_body(self.link, "private void RefreshPersonaChoices()")
        self.assertIn("new List<string>(StarterPersonas)", refresh)
        self.assertNotIn('"(none)" }', refresh)

    def test_4_memory_on_by_default(self):
        self.assertIn('new JSONStorableBool("Memory", true', self.link)

    def test_7_mic_and_ptt_interrupts_on_by_default_and_reset_tracked(self):
        self.assertIn('Enabled = Reg(new JSONStorableBool("Mic enabled", true', self.mic)
        self.assertIn('PttInterrupts = Reg(new JSONStorableBool("Push-to-talk interrupts speech", true', self.mic)
        self.assertIn("SettingsDefaults.Bool(_plugin, p)", self.mic, "Reg tracks the default for Reset to Default")


class FreshConfigTests(TestCase):
    def test_defaults(self):
        d = settings_file.DEFAULTS
        self.assertEqual(d["engines"], {"stt": "xai", "llm": "xai", "tts": "xai"})
        self.assertEqual(d["ai"]["fallback"], {"stt": "null", "llm": "echo", "tts": "tone"}, "without a key")
        self.assertEqual(d["ai"]["persona_name"], "Anna")
        self.assertTrue(d["ai"]["memory"]["enabled"])
        self.assertTrue(d["mic"]["enabled"])
        self.assertTrue(d["mic"]["ptt_interrupts"])
        self.assertTrue(MicSettings().enabled and MicSettings().ptt_interrupts)
        self.assertEqual(d["ai"]["xai"]["api_key"], "")

    def test_fresh_config_validates_without_errors(self):
        data, errors = settings_file.validate(json.loads(json.dumps(settings_file.DEFAULTS)))
        self.assertEqual(errors, [])
        self.assertEqual(data["engines"]["stt"], "xai")

    def test_example_config_and_schema_follow(self):
        example = json.loads((ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(example["engines"], {"stt": "xai", "llm": "xai", "tts": "xai"})
        self.assertEqual(example["ai"]["persona_name"], "Anna")
        self.assertTrue(example["ai"]["memory"]["enabled"])


class ResetFlowTests(TokenFlowBase):
    def capture(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logsetup.RedactingFormatter(logsetup.FORMAT, logsetup.DATEFMT))
        root = logging.getLogger()
        old = root.level
        root.setLevel(logging.DEBUG)
        root.addHandler(handler)
        self.addCleanup(root.setLevel, old)
        self.addCleanup(root.removeHandler, handler)
        return stream

    def test_reset_clears_the_token_in_the_companion_and_never_logs_it(self):
        stream = self.capture()
        self.start()
        self.plugin.set_xai_token(TOKEN)
        self.sim.run(self.plugin, 3)
        self.assertEqual(self.beat()["keys"]["xai"]["state"], "configured")
        reset_plugin(self.plugin)
        self.sim.run(self.plugin, 3)
        self.assertEqual(self.beat()["keys"]["xai"]["state"], "missing", "the reset cleared the token")
        self.assertEqual(self.app.engine_set.key("xai"), None)
        self.assertNotIn(TOKEN, stream.getvalue())
        self.assertNotIn(TOKEN, json.dumps(self.sim.sent(self.plugin, "companion_heartbeat")))
        # without a key the xai menus fall back to the test engines, and the status says why
        self.assertEqual(self.app.engine_set.active_names, {"stt": "null", "llm": "echo", "tts": "tone"})
        self.assertIn("without an xAI API key", self.beat()["mode"]["status"])

    def test_after_reset_the_menus_list_every_engine(self):
        self.start()
        reset_plugin(self.plugin)
        self.sim.run(self.plugin, 3)
        self.assertEqual(self.beat()["engines_available"], ENGINES_AVAILABLE)

    def test_after_reset_and_a_new_token_spoken_input_is_heard_and_answered(self):
        self.start()
        self.plugin.set_xai_token(TOKEN)
        self.sim.run(self.plugin, 3)
        reset_plugin(self.plugin)
        self.sim.run(self.plugin, 3)
        self.plugin.set_xai_token(TOKEN)                  # paste it again after the reset
        self.sim.run(self.plugin, 3)
        self.assertEqual(self.app.engines, {"stt": "xai", "llm": "xai", "tts": "xai"})
        self.ask()
        urls = [r.full_url for r in self.http.requests]
        for part in ("/stt", "/responses", "/tts"):
            self.assertTrue(any(u.endswith(part) for u in urls), (part, urls))
        self.assertTrue(self.app.mic_settings.enabled)
        self.assertTrue(self.app.mic_settings.ptt_interrupts)
        self.assertTrue(self.app.memory_enabled())
