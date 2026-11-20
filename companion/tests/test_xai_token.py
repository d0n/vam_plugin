"""Version 21: the plugin field "XAI API Token" (tab Voice, Voice Mode) and the "Question and Answer" button.

Token transport (config event -> companion -> xAI requests), precedence (field > XAI_API_KEY > key
file), masking (never in logs, heartbeat, config.json, errors) and the menu rules, checked on the
C# sources. Only dummy values; the "tokens" below deliberately do NOT look like keys (no format check).
"""
from __future__ import annotations

import io
import json
import logging
import re
import tempfile
import unittest
from pathlib import Path

from aibody_companion import logsetup, protocol, settings_file
from aibody_companion.pipeline.engines import EngineSet
from tests.fakes import FakeClock, FakeHttp, FakePlugin, FakeResponse, text_stream
from tests.test_plugin_menu import method_body, source
from tests.test_qa_flow import frame, pcm
from tests.test_realtime import RealtimeSim
from tests.test_e2e_simulation import Sim

TOKEN = "dummy token / no xai format 123"  # plain text: any format is accepted
ENV_KEY = "dummy-env-key-0001"
FILE_KEY = "dummy-file-key-0002"
OTHER = "dummy-other-token-0003"


class TokenFlowBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.clock = FakeClock()
        self.http = FakeHttp()
        self.http.route("/stt", lambda r: FakeResponse(json.dumps({"text": "Hello?"}).encode()))
        self.http.route("/responses", lambda r: FakeResponse(text_stream(["Hi there. "]), "text/event-stream"))
        self.http.route("/tts", lambda r: FakeResponse(pcm(0.5), "audio/pcm"))

    def tearDown(self):
        if getattr(self, "app", None):
            self.app.shutdown()
        self.tmp.cleanup()
        logsetup._SECRETS.clear()

    def start(self, env=None):
        self.sim = Sim(self.tmp.name, self.clock, self.http, env=env or {}, mode="qa")
        self.app = self.sim.start_app()
        self.plugin = FakePlugin(self.root, self.clock, mode="qa")
        self.plugin.start()
        self.sim.run(self.plugin, 3)

    def push(self, seconds=2.5):
        self.plugin.send_config()
        self.sim.run(self.plugin, seconds)

    def beat(self):
        return self.sim.sent(self.plugin, "companion_heartbeat")[-1]

    def ask(self):
        """A spoken question: speech to text -> Grok -> text to speech, all with the current key."""
        self.http.requests.clear()
        for loud in [True] * 40 + [False] * 30:
            self.app.handle_audio_frame(frame(loud))
        self.sim.run(self.plugin, 4)

    def auth_headers(self):
        return {r.get_header("Authorization") for r in self.http.requests}


class TokenTransportTests(TokenFlowBase):
    def test_token_travels_in_the_config_event_file_and_is_used_for_xai_calls(self):
        self.start()
        self.assertEqual(self.beat()["keys"]["xai"]["state"], "missing")
        outbox_before = set(self.plugin.outbox.glob("*.json"))
        self.plugin.set_xai_token(TOKEN)
        written = [json.loads(f.read_text()) for f in set(self.plugin.outbox.glob("*.json")) - outbox_before]
        self.assertEqual([w["keys"] for w in written if w["type"] == "config"], [{"xai": TOKEN}],
                         "the token is in the file transport's config event as typed")
        self.sim.run(self.plugin, 2.5)
        keys = self.beat()["keys"]["xai"]
        self.assertEqual(keys["state"], "configured")
        self.assertIn("XAI API Token", keys["detail"])
        self.ask()
        self.assertTrue(self.requests("/stt") and self.requests("/responses") and self.requests("/tts"))
        self.assertEqual(self.auth_headers(), {f"Bearer {TOKEN}"}, "every xAI call uses the field's token")
        self.assertTrue(self.sim.sent(self.plugin, "speak"), "the answer is spoken")

    def requests(self, part):
        return [r for r in self.http.requests if part in r.full_url]

    def test_any_format_is_accepted_and_blanks_are_stripped(self):
        self.start()
        self.plugin.set_xai_token("  not-a-key-at-all  \n")
        self.sim.run(self.plugin, 2.5)
        self.assertEqual(self.app.engine_set.key("xai"), "not-a-key-at-all")
        self.assertEqual(self.beat()["keys"]["xai"]["state"], "configured")
        short = "x"
        self.plugin.set_xai_token(short)
        self.sim.run(self.plugin, 2.5)
        self.assertEqual(self.app.engine_set.key("xai"), "x")

    def test_clearing_the_field_removes_the_token(self):
        self.start()
        self.plugin.set_xai_token(TOKEN)
        self.sim.run(self.plugin, 2.5)
        self.plugin.set_xai_token("")
        self.sim.run(self.plugin, 2.5)
        self.assertIsNone(self.app.engine_set.key("xai"))
        self.assertEqual(self.beat()["keys"]["xai"]["state"], "missing")

    def test_token_arrives_again_after_a_companion_restart(self):
        self.start()
        self.plugin.set_xai_token(TOKEN)
        self.sim.run(self.plugin, 2.5)
        self.app.shutdown()
        self.app = self.sim.start_app()  # new session: the plugin resends ready + config
        self.assertIsNone(self.app.engine_set.key("xai"))
        self.plugin.epoch += 1
        self.sim.run(self.plugin, 3)
        self.assertEqual(self.app.engine_set.key("xai"), TOKEN)

    def test_token_is_not_written_to_config_json(self):
        self.start()
        self.plugin.set_xai_token(TOKEN)
        self.sim.run(self.plugin, 2.5)
        self.plugin.write_settings()
        raw = settings_file.settings_path(self.tmp.name).read_text()
        self.assertNotIn(TOKEN, raw)
        self.assertNotIn("keys", json.loads(raw))
        self.assertEqual(json.loads(raw)["ai"]["xai"].get("key_file", ""), "")
        self.assertNotIn(TOKEN, json.dumps(self.beat()), "never in the heartbeat")

    def test_key_file_fields_still_refuse_a_pasted_key(self):
        data, errors = settings_file.validate({"ai": {"xai": {"key_file": "xai-FAKE-NOT-A-KEY"}}})
        self.assertEqual(data["ai"]["xai"]["key_file"], "")
        self.assertTrue(errors)

    def test_bad_keys_payload_is_reported_without_the_token(self):
        self.start()
        self.app.handle_config({"type": "config", "mic": {}, "keys": {"xai": 12345}})
        self.app.handle_config({"type": "config", "mic": {}, "keys": "nope"})
        acks = self.sim.sent(self.plugin, "config_ack")
        self.sim.run(self.plugin, 0.5)
        acks = self.sim.sent(self.plugin, "config_ack")
        errors = [e for a in acks for e in a.get("errors", [])]
        self.assertIn("keys.xai: must be a string", errors)
        self.assertIn("keys: must be an object", errors)

    def test_config_event_without_keys_leaves_the_token(self):
        self.start()
        self.plugin.set_xai_token(TOKEN)
        self.sim.run(self.plugin, 2.5)
        self.app.handle_config({"type": "config", "mic": {}})  # an older plugin
        self.assertEqual(self.app.engine_set.key("xai"), TOKEN)


class PrecedenceTests(TokenFlowBase):
    def key_file(self, text=FILE_KEY):
        path = self.root / "xai.key"
        path.write_text(text + "\n")
        self.plugin.key_files["xai"] = str(path)

    def test_field_beats_environment_beats_key_file(self):
        self.start(env={"XAI_API_KEY": ENV_KEY})
        self.key_file()
        self.push()
        self.assertEqual(self.app.engine_set.key("xai"), ENV_KEY, "no field: the environment variable wins over the key file")
        self.plugin.set_xai_token(TOKEN)
        self.sim.run(self.plugin, 2.5)
        self.assertEqual(self.app.engine_set.key("xai"), TOKEN, "the field wins over both")
        self.ask()
        self.assertEqual(self.auth_headers(), {f"Bearer {TOKEN}"})
        self.plugin.set_xai_token("")
        self.sim.run(self.plugin, 2.5)
        self.assertEqual(self.app.engine_set.key("xai"), ENV_KEY, "empty field: back to the environment variable")
        self.ask()
        self.assertEqual(self.auth_headers(), {f"Bearer {ENV_KEY}"})

    def test_key_file_is_used_when_field_and_environment_are_empty(self):
        self.start()
        self.key_file()
        self.push()
        self.assertEqual(self.app.engine_set.key("xai"), FILE_KEY)
        self.assertIn("key file", self.beat()["keys"]["xai"]["detail"])
        self.plugin.set_xai_token(OTHER)
        self.sim.run(self.plugin, 2.5)
        self.assertEqual(self.app.engine_set.key("xai"), OTHER)

    def test_unit_engine_set(self):
        engines = EngineSet({}, env={"XAI_API_KEY": ENV_KEY})
        self.assertEqual(engines.key("xai"), ENV_KEY)
        self.assertTrue(engines.set_ui_key("xai", TOKEN))
        self.assertEqual(engines.key("xai"), TOKEN)
        self.assertFalse(engines.set_ui_key("xai", f" {TOKEN} "), "same token, nothing changed")
        self.assertTrue(engines.set_ui_key("xai", ""))
        self.assertEqual(engines.key("xai"), ENV_KEY)
        self.assertFalse(engines.set_ui_key("elevenlabs", OTHER), "no ElevenLabs field")
        self.assertIsNone(engines.key("elevenlabs"))
        self.assertNotIn(TOKEN, json.dumps(engines.key_info()))

    def test_a_rejected_token_gets_replaced_by_a_new_one(self):
        engines = EngineSet({}, env={})
        engines.set_ui_key("xai", TOKEN)
        engines.rejected["xai"] = "rejected by the server (HTTP 401)"
        self.assertEqual(engines.key_info()["xai"]["state"], "rejected")
        engines.set_ui_key("xai", OTHER)
        self.assertEqual(engines.key_info()["xai"]["state"], "configured")


class MaskingTests(TokenFlowBase):
    def capture(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logsetup.RedactingFormatter(logsetup.FORMAT, logsetup.DATEFMT))
        records = []

        class Keep(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        root = logging.getLogger()
        old = root.level
        root.setLevel(logging.DEBUG)
        root.addHandler(handler)
        root.addHandler(Keep())
        self.addCleanup(root.setLevel, old)
        self.addCleanup(root.removeHandler, handler)
        return stream, records

    def test_token_never_reaches_the_log_even_for_a_broken_event(self):
        stream, records = self.capture()
        self.start()
        self.plugin.send("config", keys={"xai": TOKEN})  # no 'mic': the app ignores it and logs why
        self.plugin.set_xai_token(OTHER)
        self.sim.run(self.plugin, 3)
        self.ask()
        text = stream.getvalue()
        self.assertIn("Ignoring event", text)
        self.assertIn("XAI API Token from the plugin field set", text)
        for secret in (TOKEN, OTHER):
            self.assertNotIn(secret, text, "formatted log lines")
            self.assertFalse([r for r in records if secret in r], "not even the raw log records")

    def test_loggable_masks_the_values(self):
        event = {"type": "config", "keys": {"xai": TOKEN}, "mic": {}}
        self.assertEqual(protocol.loggable(event)["keys"], {"xai": "***"})
        self.assertEqual(event["keys"]["xai"], TOKEN, "the original is untouched")
        self.assertEqual(protocol.loggable({"type": "ptt"}), {"type": "ptt"})

    def test_redact_masks_a_registered_token_in_any_text(self):
        protocol.register_event_secrets({"keys": {"xai": f" {TOKEN} "}})
        self.assertEqual(logsetup.redact(f"failed with {TOKEN} here"), "failed with *** here")
        logsetup._SECRETS.clear()

    def test_the_status_never_contains_the_token(self):
        self.start()
        self.plugin.set_xai_token(TOKEN)
        self.sim.run(self.plugin, 2.5)
        everything = json.dumps(self.sim.sent(self.plugin, "companion_heartbeat")) + json.dumps(
            self.sim.sent(self.plugin, "config_ack"))
        self.assertNotIn(TOKEN, everything)


class RealtimeTokenTests(RealtimeSim):
    def test_realtime_connects_with_the_field_token(self):
        self.start(mode="auto", env={})
        self.pump(timeout=0.5)
        self.assertNotEqual(self.app.active_mode, "realtime")
        self.plugin.set_xai_token(TOKEN)
        self.connect()
        self.assertEqual(self.server.conn.headers["authorization"], f"Bearer {TOKEN}")


class PluginSourceTests(unittest.TestCase):
    def test_token_field_sits_below_api_reconnect_without_warning_label_under_it(self):
        body = method_body(source("AppLink.cs"), "public void BuildConnectionSection(UiPage page)")
        order = [body.index(s) for s in ('page.Button("API Reconnect"', "page.Header(XaiTokenLabel)", "page.TextInputField(_xaiTokenJson)")]
        self.assertEqual(order, sorted(order))
        # 20.11.2026 (Leon): the hint left the right column; it is running prose in the left field of the tab Voice
        self.assertNotIn("XaiTokenHint", body)
        self.assertIn("XaiTokenHint", method_body(source("AppLink.cs"), "public string VoiceInfoText()"))
        self.assertNotIn("XaiTokenWarning", body, "the security notice is in the big info field, not under the token field")
        link = source("AppLink.cs")
        self.assertIn('XaiTokenLabel = "XAI API Token"', link)
        self.assertNotIn("beware: scenes save it", link)

    def test_plain_text_field_without_format_check(self):
        link = source("AppLink.cs")
        self.assertIn('new JSONStorableString(XaiTokenLabel, "", OnTokenEdited)', link)
        self.assertNotIn("LooksLikeKey(XaiToken", link)
        self.assertNotIn("LooksLikeKey(_xaiTokenJson", link)
        self.assertNotIn("LooksLikeKey(typed", link)
        self.assertNotIn("RegisterString(_xaiTokenJson)", link, "version 31: the field is not registered, so the scene never holds the token")
        edited = method_body(link, "private void OnTokenEdited(string v)")
        self.assertIn("Trim()", edited)
        self.assertNotRegex(edited, r"Regex|StartsWith|Length >=")

    def test_token_goes_to_the_config_event_and_to_config_json_only_as_ai_xai_api_key(self):
        link = source("AppLink.cs")
        self.assertIn('keys["xai"] = XaiToken;', method_body(link, "private void AddEngines(JSONClass configEvent)"))
        ai = method_body(link, "private JSONClass BuildAiJson(bool forFile)")
        self.assertIn('if (forFile && _tokenReady)', ai, "never in the config event, never before config.json was read")
        self.assertIn('xai["api_key"] = _xaiToken;', ai)
        self.assertIn('xai["api_key_warning"] = XaiTokenWarningPlain;', ai)
        self.assertIn("BuildAiJson(false)", method_body(link, "private void AddEngines(JSONClass configEvent)"))
        merge = method_body(link, "public static void MergeAi(JSONClass target, JSONClass ui)")
        self.assertIn('"xai", "api_key")', merge)
        self.assertIn('"xai", "api_key_warning")', merge, "the write-back keeps the warning next to the token")
        self.assertNotIn("_xaiTokenJson", merge)
        self.assertNotIn("_xaiTokenJson", method_body(link, "public void ApplySettings(JSONClass root)"))

    def test_token_is_never_logged_by_the_plugin(self):
        link = source("AppLink.cs")
        send = method_body(link, "public void Send(JSONClass evt)")
        self.assertIn("LogText(evt)", send)
        self.assertNotIn("evt.ToString()", send)
        self.assertIn("keys masked", method_body(link, "private string LogText(JSONClass evt)"))
        for name in ("AIBody.cs", "AppLink.cs", "Body.cs", "MicConfig.cs", "FileTransport.cs"):
            for line in source(name).splitlines():
                if re.search(r"Log\.(Info|Debug|Error|Warn)\(", line):
                    self.assertNotRegex(line, r"_xaiTokenJson|XaiToken\b(?!Label|Hint)", f"{name}: {line.strip()}")

    def test_no_elevenlabs_field(self):
        link = source("AppLink.cs")
        self.assertNotRegex(link, r"ElevenLabs API Token|_elevenTokenJson")
        for file, sig in (("AppLink.cs", "public void BuildConnectionSection(UiPage page)"),
                          ("AppLink.cs", "public void BuildAiSection(UiPage page)"),
                          ("AppLink.cs", "public void BuildVoiceSection(UiPage page)")):
            self.assertNotIn("Eleven", method_body(source(file), sig))

    def test_question_and_answer_button_is_centered_on_two_lines(self):
        plugin = source("AIBody.cs")
        self.assertIn('QaButtonLabel = "Question\\n& Answer"', plugin)
        voice = method_body(plugin, "private void ShowTab(int index)")
        self.assertIn("_page.Button(QaButtonLabel, ", voice)
        self.assertNotIn("Simple Q&A mode", voice)
        helper = source("UiHelper.cs")
        two_line = method_body(helper, "public void Button(string label, float height, UnityEngine.Events.UnityAction onClick)")
        self.assertIn("buttonText.alignment = UnityEngine.TextAnchor.MiddleCenter", two_line)
        self.assertIn("b.height = height", two_line)
        self.assertIn("EnableSimpleQa", voice, "function unchanged: same handler")
        enable = method_body(plugin, "private void EnableSimpleQa()")
        self.assertIn("_link.SetSimpleQa()", enable)
        self.assertIn("SetBodyControl(false)", enable)
        self.assertIn("_aiModeJson.val = ModeQa", method_body(source("AppLink.cs"), "public void SetSimpleQa()"))


if __name__ == "__main__":
    unittest.main()
