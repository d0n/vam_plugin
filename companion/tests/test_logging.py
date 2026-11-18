"""Verbose conversation logging: redaction, levels, the log file, and the per-turn trace end to end."""
from __future__ import annotations

import io
import json
import logging
import re
import tempfile
import unittest
from pathlib import Path

from aibody_companion import logsetup, settings_file
from aibody_companion.pipeline.http import is_key_rejection
from tests.fakes import http_error
from tests.test_qa_flow import KEY, QaFlowTests
from tests.test_realtime import RealtimeSim, tone

TRACE_LINE = re.compile(r"\[(t\d{4})(?: \+\d+\.\d\ds)?\] ([^:]+)")


class RedactionTests(unittest.TestCase):
    def test_registered_key_and_key_shapes_are_masked(self):
        logsetup.add_secret("my-very-own-secret-123")
        self.assertEqual(logsetup.redact("key my-very-own-secret-123 used"), "key *** used")
        self.assertNotIn("abcdefgh123", logsetup.redact("Authorization: Bearer abcdefgh123"))
        self.assertIn("Bearer ***", logsetup.redact("Authorization: Bearer abcdefgh123"))
        self.assertEqual(logsetup.redact("x xai-AbCdEf123456789 y"), "x *** y")
        self.assertEqual(logsetup.redact("sk_0123456789abcdef"), "***")
        self.assertIn("***", logsetup.redact('{"xi-api-key": "0123456789abcdef"}'))
        self.assertNotIn("0123456789abcdef", logsetup.redact("api_key=0123456789abcdef"))
        self.assertEqual(logsetup.redact("Wie spät ist es? t0001 utt-17-1"), "Wie spät ist es? t0001 utt-17-1")
        logsetup.add_secret("abc")  # too short to be a key: ignored, normal words stay readable
        self.assertEqual(logsetup.redact("abc"), "abc")

    def test_exceptions_in_the_log_are_redacted_too(self):
        stream = io.StringIO()
        logsetup.setup(None, stream=stream)
        try:
            try:
                raise RuntimeError("request failed with key xai-SECRETSECRETSECRET")
            except RuntimeError:
                logging.getLogger("aibody_companion.test").exception("boom %s", "Bearer tok-123456789")
        finally:
            logsetup.teardown()
        out = stream.getvalue()
        self.assertIn("boom", out)
        self.assertNotIn("SECRETSECRET", out)
        self.assertNotIn("tok-123456789", out)

    def test_xai_wrong_key_answer_counts_as_rejected(self):
        self.assertTrue(is_key_rejection(400, "Incorrect API key provided. You can obtain an API key from …"))
        self.assertTrue(is_key_rejection(401, ""))
        self.assertFalse(is_key_rejection(400, "Messages cannot be empty"))
        self.assertFalse(is_key_rejection(500, "api key"))


class LevelAndFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        logsetup.teardown()
        self.tmp.cleanup()

    def test_log_file_next_to_config_and_trace_only_when_verbose(self):
        stream = io.StringIO()
        path = logsetup.setup(self.tmp.name, stream=stream)
        self.assertEqual(path, Path(self.tmp.name) / "Saves/PluginData/AIBody/logs/companion.log")
        self.assertEqual(logsetup.log_file(), path)
        self.assertFalse(logsetup.is_verbose())
        logsetup.Turn("text", text="eins").step("path", mode="qa")
        logging.getLogger("aibody_companion.x").debug("debug hidden")
        logging.getLogger("aibody_companion.x").info("info shown")
        self.assertTrue(logsetup.set_verbose(True))
        turn = logsetup.Turn("text", text="zwei")
        turn.step("stt", engine="xai", ms=812, text="Wie spät ist es?")
        logsetup.trace(turn.id, "plugin: speech_started", duration=1.5)
        self.assertTrue(logsetup.set_verbose(False))
        logsetup.Turn("text", text="drei")
        for h in logging.getLogger().handlers:
            h.flush()
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text, stream.getvalue(), "console and file get the same lines")
        self.assertIn("info shown", text)
        self.assertNotIn("debug hidden", text)
        self.assertNotIn("eins", text)
        self.assertNotIn("drei", text)
        self.assertIn(f"[{turn.id} +0.00s] start: kind='text' text='zwei'", text)
        self.assertIn("stt: engine='xai' ms=812 text='Wie spät ist es?'", text)
        self.assertIn(f"[{turn.id}] plugin: speech_started: duration=1.5", text)
        self.assertIn("Verbose log on (turn trace) - log file", text)
        self.assertRegex(text, r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} INFO ")

    def test_debug_forces_the_trace_on(self):
        logsetup.setup(None, debug=True, stream=io.StringIO())
        self.assertTrue(logsetup.is_verbose())
        logsetup.set_verbose(False)
        self.assertTrue(logsetup.is_verbose(), "--verbose keeps the trace on")
        self.assertEqual(logging.getLogger().level, logging.DEBUG)

    def test_missing_vam_folder_means_console_only(self):
        self.assertIsNone(logsetup.setup(str(Path(self.tmp.name) / "nope"), stream=io.StringIO()))


class TurnTraceE2ETests(QaFlowTests):
    """The QaFlow simulation (fake plugin, fake xAI) with the plugin's "Verbose log" toggle on."""

    def setUp(self):
        super().setUp()
        self.stream = io.StringIO()
        logsetup.setup(self.tmp.name, stream=self.stream)

    def tearDown(self):
        logsetup.teardown()
        super().tearDown()

    def lines(self):
        return [ln for ln in self.stream.getvalue().splitlines() if "aibody_companion.trace" in ln]

    def steps(self, turn_id):
        out = []
        for ln in self.lines():
            m = TRACE_LINE.search(ln)
            if m and m.group(1) == turn_id:
                out.append(m.group(2))
        return out

    def turn_ids(self):
        return list(dict.fromkeys(m.group(1) for m in map(TRACE_LINE.search, self.lines()) if m))

    def verbose_on(self):
        self.plugin.set_verbose(True)
        self.sim.run(self.plugin, 1)
        self.assertTrue(logsetup.is_verbose())
        ack = [e for e in self.sim.sent(self.plugin, "config_ack")][-1]
        self.assertEqual(ack["applied"]["advanced"], {"verbose_log": True})
        raw = json.loads(settings_file.settings_path(self.tmp.name).read_text())
        self.assertIn(raw["advanced"]["verbose_log"], (True, "true"))

    def test_spoken_turn_is_traced_step_by_step_with_one_turn_id(self):
        self.start()
        self.speak_mic_question()
        self.assertEqual(self.lines(), [], "verbose is off by default: no trace")
        self.verbose_on()
        self.speak_mic_question()
        (tid,) = self.turn_ids()
        steps = self.steps(tid)
        for want in ["start", "path", "stt", "llm request", "llm tag", "llm sentence 1", "llm sentence 2",
                     "tts", "speak sent", "end", "plugin", "plugin"]:
            self.assertTrue(any(s.startswith(want) for s in steps), f"{want!r} missing in {steps}")
        self.assertLess(steps.index("start"), steps.index("path"))
        self.assertLess(steps.index("path"), steps.index("stt"))
        self.assertLess(steps.index("stt"), steps.index("llm request"))
        text = "\n".join(self.lines())
        self.assertIn("kind='audio' seconds=", text)
        self.assertIn("rms=", text)
        self.assertIn("mode='qa' active='chain'", text)
        self.assertIn("text='Wie spät ist es?'", text)
        self.assertIn("dropped", text)
        self.assertIn("voice='eve'", text)
        self.assertIn("wav='Custom/Sounds/AIBody/default/utt-", text)
        self.assertIn("plugin: speech_started", text)
        self.assertIn("plugin: speech_ended", text)
        self.assertNotIn(KEY, self.stream.getvalue())
        self.assertNotIn(KEY, (Path(self.tmp.name) / "Saves/PluginData/AIBody/logs/companion.log")
                         .read_text(encoding="utf-8"))

    def test_typed_turn_and_failure_are_traced(self):
        self.http.route("/tts", lambda r: (_ for _ in ()).throw(
            http_error(r.full_url, 400, {"error": "Incorrect API key provided."})))
        self.start()
        self.verbose_on()
        self.app.handle_user_text("Hallo")
        self.sim.run(self.plugin, 3)
        (tid,) = self.turn_ids()
        text = "\n".join(self.lines())
        self.assertIn(f"[{tid} +0.00s] start: kind='text' text='Hallo'", text)
        self.assertIn("engine='xai failed -> fallback'", text)
        self.assertNotIn("stt:", text)
        self.assertNotIn(KEY, self.stream.getvalue())
        self.assertEqual(self.app.engine_set.key_info().get("xai", {}).get("state"), "rejected",
                         "xAI answers a wrong key with HTTP 400 'Incorrect API key'")

    def test_toggle_off_stops_the_trace(self):
        self.start()
        self.verbose_on()
        self.plugin.set_verbose(False)
        self.sim.run(self.plugin, 1)
        self.assertFalse(logsetup.is_verbose())
        self.app.handle_user_text("Hallo")
        self.sim.run(self.plugin, 3)
        self.assertEqual(self.turn_ids(), [])

    # QaFlowTests' own tests run in their own class; here only the trace tests
    for _name in [n for n in dir(QaFlowTests) if n.startswith("test_")]:
        locals()[_name] = None
    del _name


class RealtimeToggleTests(QaFlowTests):
    """Voice Mode > "Echtzeit (Realtime) verwenden": on = mode auto, off = qa (the default)."""

    for _name in [n for n in dir(QaFlowTests) if n.startswith("test_")]:
        locals()[_name] = None
    del _name

    def test_toggle_maps_to_the_ai_mode(self):
        self.start()
        self.assertEqual(self.app.mode_requested, "qa")
        self.plugin.set_realtime(True)
        self.sim.run(self.plugin, 1)
        self.assertEqual(self.app.mode_requested, "auto")
        raw = json.loads(settings_file.settings_path(self.tmp.name).read_text())
        self.assertEqual(raw["ai"]["mode"], "auto")
        self.plugin.set_realtime(False)
        self.sim.run(self.plugin, 1)
        self.assertEqual(self.app.mode_requested, "qa")
        self.plugin.ai_ui["mode"] = "realtime"
        self.plugin.set_realtime(True)
        self.assertEqual(self.plugin.ai_ui["mode"], "realtime", "already on: an explicit realtime stays")


class RealtimeTraceTests(RealtimeSim):
    def test_realtime_events_and_segments_share_one_turn_id(self):
        stream = io.StringIO()
        logsetup.setup(self.tmp.name, stream=stream)
        self.addCleanup(logsetup.teardown)
        self.start()
        self.connect()
        self.plugin.set_verbose(True)
        self.assertTrue(self.pump(logsetup.is_verbose))
        self.server.respond(["Hallo! ", "Wie war dein Tag?"], tone(3.0))
        self.assertTrue(self.pump(lambda: self.app.realtime.response_id is None
                                  and sum(s["duration"] for s in self.speaks()) > 2.99))
        self.pump(lambda: "plugin: speech_ended" in stream.getvalue())
        lines = [ln for ln in stream.getvalue().splitlines() if "aibody_companion.trace" in ln]
        ids = {m.group(1) for m in (re.search(r"\[(rt\d{4})", ln) for ln in lines) if m}
        self.assertEqual(len(ids), 1, lines)
        text = "\n".join(lines)
        for want in ["realtime response.created", "realtime response.done", "answer_audio_s=3",
                     "speak sent", "plugin: speech_started"]:
            self.assertIn(want, text)
        self.assertNotIn(KEY, stream.getvalue())


del QaFlowTests, RealtimeSim  # not collected twice
