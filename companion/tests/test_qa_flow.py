"""The simple question-and-answer flow end to end, without VaM and without network:

  mic audio (local VAD) or typed text -> fake xAI speech to text -> fake Grok (streamed, split
  into sentences) -> fake xAI text to speech -> WAV in the audio folder -> speak -> fake plugin

plus its failure cases (nothing understood, language model / text to speech errors), the audio
folder switch when VaM cannot load the WAVs, and the chain fallback when realtime does not answer.
The engine menus stay on their defaults (null / echo / tone): mode qa uses xai with a key anyway.
"""
from __future__ import annotations

import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from aibody_companion import settings_file
from aibody_companion.orchestrator import LLM_ERROR_SAY
from tests.fakes import FakeClock, FakeHttp, FakePlugin, FakeResponse, http_error, text_stream
from tests.test_e2e_simulation import Sim
from tests.test_realtime import RealtimeSim

KEY = "xai-FAKE-NOT-A-KEY-qa"


def frame(loud: bool, ms: int = 30, rate: int = 16000) -> bytes:
    n = rate * ms // 1000
    amp = 6000 if loud else 0
    return struct.pack(f"<{n}h", *(int(amp * math.sin(i / 3)) for i in range(n)))


def pcm(seconds: float, rate: int = 24000) -> bytes:
    return b"\x10\x00" * int(seconds * rate)


class QaFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.clock = FakeClock()
        self.http = FakeHttp()
        self.http.route("/stt", lambda r: FakeResponse(json.dumps({"text": "Wie spät ist es?"}).encode()))
        self.http.route("/responses", lambda r: FakeResponse(
            text_stream(["<<happy nod>>Es ist kurz vor sieben. ", "Noch etwas?"]), "text/event-stream"))
        self.http.route("/tts", lambda r: FakeResponse(pcm(0.8), "audio/pcm"))

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, env=None):
        self.sim = Sim(self.tmp.name, self.clock, self.http, env={"XAI_API_KEY": KEY} if env is None else env,
                       mode="qa")
        self.app = self.sim.start_app()
        self.plugin = FakePlugin(self.root, self.clock, mode="qa")
        self.plugin.start()
        self.sim.run(self.plugin, 3)
        self.assertTrue(self.plugin.app_alive)
        return self.app

    def speak_mic_question(self):
        for loud in [True] * 40 + [False] * 30:
            self.app.handle_audio_frame(frame(loud))
        self.sim.run(self.plugin, 4)

    def speaks(self):
        return self.sim.sent(self.plugin, "speak")

    def requests(self, part):
        return [r for r in self.http.requests if part in r.full_url]

    def assert_played(self, speak, rate=24000):
        wav = self.root / speak["audio"]
        self.assertTrue(speak["audio"].startswith("Custom/Sounds/AIBody/default/"), speak["audio"])
        with wave.open(str(wav), "rb") as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, rate))
            self.assertAlmostEqual(w.getnframes() / rate, speak["duration"], places=2)
        self.assertIn(("started", speak["id"]), self.plugin.speech_events)

    # -- the happy path ----------------------------------------------------------------------

    def test_spoken_question_is_answered_audibly(self):
        app = self.start()
        self.assertEqual(app.engine_set.active_names, {"stt": "xai", "llm": "xai", "tts": "xai"})
        self.assertEqual(app.engines, {"stt": "xai", "llm": "xai", "tts": "xai"}, "the menus stay as they are (v50 default xai)")
        self.speak_mic_question()
        stt = self.requests("/stt")
        self.assertEqual(len(stt), 1)
        self.assertIn(b"RIFF", stt[0].data, "the utterance goes to speech to text as WAV")
        llm = json.loads(self.requests("/responses")[0].data)
        self.assertTrue(llm["stream"])
        self.assertIn("Wie spät ist es?", json.dumps(llm["input"], ensure_ascii=False))
        speaks = self.speaks()
        self.assertEqual([s["text"] for s in speaks], ["Es ist kurz vor sieben.", "Noch etwas?"])
        self.assertEqual(len(self.requests("/tts")), 2, "one TTS request per sentence")
        for s in speaks:
            self.assert_played(s)
        self.assertEqual(self.sim.sent(self.plugin, "expression") + self.sim.sent(self.plugin, "gesture"), [],
                         "simple Q&A: speech only, the <<happy nod>> tag is dropped")
        self.assertIn("Answer (2 sentence(s), xai -> xai)", self.plugin.turn)
        beat = self.sim.sent(self.plugin, "companion_heartbeat")[-1]
        self.assertEqual(beat["mode"]["requested"], "qa")
        self.assertIn("Question and Answer", beat["mode"]["status"])
        self.assertEqual(beat["proactive"]["status"], "paused in Question and Answer mode")
        self.assertEqual(beat["audio_out"], {"folder": "Custom/Sounds/AIBody/default", "auto": True})

    def test_typed_text_takes_the_same_path_without_speech_to_text(self):
        self.start()
        self.app.handle_user_text("Hallo")
        self.sim.run(self.plugin, 3)
        self.assertEqual(self.requests("/stt"), [])
        self.assertIn("Hallo", json.dumps(json.loads(self.requests("/responses")[0].data)["input"]))
        speaks = self.speaks()
        self.assertEqual(len(speaks), 2)
        for s in speaks:
            self.assert_played(s)

    def test_qa_is_the_default_and_the_button_turns_body_control_off(self):
        self.sim = Sim(self.tmp.name, self.clock, self.http, env={"XAI_API_KEY": KEY})
        self.sim.start_app().shutdown()
        data = json.loads(settings_file.settings_path(self.tmp.name).read_text())
        self.assertEqual(data["ai"]["mode"], "qa")
        self.assertEqual(data["connection"]["paths"]["audio"], "")
        # a scene from 0.7.1 (mode auto) + the button "Simple Q&A mode"
        self.app = Sim(self.tmp.name, self.clock, self.http, env={"XAI_API_KEY": KEY}, mode="auto").start_app()
        self.plugin = FakePlugin(self.root, self.clock, mode="auto")
        self.plugin.start()
        self.sim.app = self.app
        self.sim.run(self.plugin, 3)
        self.plugin.simple_qa()
        self.sim.run(self.plugin, 1)
        self.assertEqual(self.app.mode_requested, "qa")
        raw = json.loads(settings_file.settings_path(self.tmp.name).read_text())
        self.assertEqual((raw["ai"]["mode"], raw["body"]["body_control"]), ("qa", "false"))

    # -- failures ------------------------------------------------------------------------------

    def test_nothing_understood(self):
        self.http.route("/stt", lambda r: FakeResponse(b'{"text": "  "}'))
        self.start()
        self.speak_mic_question()
        self.assertEqual(self.requests("/responses"), [], "no question, no model request")
        self.assertEqual(self.speaks(), [])
        self.assertIn("Nothing understood", self.plugin.turn)

    def test_speech_to_text_error_is_reported(self):
        self.http.route("/stt", lambda r: http_error(r.full_url, 500, {"error": "stt down"}))
        self.start()
        self.speak_mic_question()
        self.assertEqual(self.speaks(), [])
        self.assertIn("Speech recognition error", self.plugin.turn)
        self.assertIn("stt down", self.plugin.turn)

    def test_language_model_error_is_said_aloud(self):
        self.http.route("/responses", lambda r: http_error(r.full_url, 503, {"error": "overloaded"}))
        self.start()
        self.app.handle_user_text("Hallo")
        self.sim.run(self.plugin, 3)
        speaks = self.speaks()
        self.assertEqual([s["text"] for s in speaks], [LLM_ERROR_SAY["de"]])
        self.assert_played(speaks[0])
        self.assertIn("Language model error", self.plugin.turn)
        self.assertIn("fallback answer", self.plugin.turn)

    def test_language_model_network_error_is_not_silent(self):
        def boom(r):
            raise ConnectionResetError("connection reset by peer")
        self.http.route("/responses", boom)
        self.start()
        self.app.handle_user_text("Hallo")
        self.sim.run(self.plugin, 3)
        self.assertEqual([s["text"] for s in self.speaks()], [LLM_ERROR_SAY["de"]])
        self.assertIn("Language model error", self.plugin.turn)

    def test_text_to_speech_error_plays_the_fallback_tone(self):
        self.http.route("/tts", lambda r: http_error(r.full_url, 500, {"error": "tts down"}))
        self.start()
        self.app.handle_user_text("Hallo")
        self.sim.run(self.plugin, 6)
        speaks = self.speaks()
        self.assertEqual([s["text"] for s in speaks], ["Es ist kurz vor sieben.", "Noch etwas?"])
        for s in speaks:
            self.assertGreater(s["duration"], 0.3)
            self.assertIn(("started", s["id"]), self.plugin.speech_events)
        self.assertIn("Text-to-speech error", self.plugin.turn)
        self.assertIn("fallback tone (tone)", self.plugin.turn)

    def test_without_key_the_test_engines_run_and_the_status_says_why(self):
        self.start(env={})
        self.assertEqual(self.app.engine_set.active_names, {"stt": "null", "llm": "echo", "tts": "tone"})
        self.app.handle_user_text("Hallo")
        self.sim.run(self.plugin, 3)
        self.assertEqual([s["text"] for s in self.speaks()], ["You said: Hallo"])
        beat = self.sim.sent(self.plugin, "companion_heartbeat")[-1]
        self.assertIn("without an xAI API key", beat["mode"]["status"])
        self.speak_mic_question()
        self.assertIn("speech recognition 'null'", self.plugin.turn)

    # -- audio folder ----------------------------------------------------------------------------

    def test_unloadable_folder_switches_to_plugin_data_once(self):
        self.start()
        self.plugin.unloadable = ("Custom/",)
        self.plugin.request_test_tone()
        self.sim.run(self.plugin, 3)
        speaks = self.speaks()
        self.assertEqual(len(speaks), 2, "the same tone is sent again from the other folder")
        self.assertTrue(speaks[0]["audio"].startswith("Custom/Sounds/AIBody/default/"))
        self.assertTrue(speaks[1]["audio"].startswith("Saves/PluginData/AIBody/default/audio/"))
        self.assertTrue((self.root / speaks[1]["audio"]).is_file())
        self.assertIn(("started", speaks[1]["id"]), self.plugin.speech_events)
        self.assertEqual(self.plugin.audio_out["folder"], "Saves/PluginData/AIBody/default/audio")
        self.assertIn("now writes them to", self.plugin.audio_out["note"])
        # the answers now go to the new folder
        self.app.handle_user_text("Hallo")
        self.sim.run(self.plugin, 3)
        self.assertTrue(all(s["audio"].startswith("Saves/") for s in self.speaks()[2:]))
        self.assertEqual(len(self.speaks()), 4)

    def test_both_folders_unloadable_is_reported_without_a_loop(self):
        self.start()
        self.plugin.unloadable = ("Custom/", "Saves/")
        self.plugin.request_test_tone()
        self.sim.run(self.plugin, 3)
        self.assertEqual(len(self.speaks()), 2)
        self.assertIn("could not play the speech files from either", self.plugin.audio_out["note"])
        note = self.plugin.audio_out["note"]
        self.assertNotIn("TEST_PROTOCOL", note, "Don took 'T9' for a log")
        self.assertIn("Saves/PluginData/AIBody/logs/companion.log", note)
        self.assertIn("'Play test tone' (tab Voice)", note)
        self.assertIn("--vam-root", note)

    def test_fixed_audio_folder_is_not_switched(self):
        self.sim = Sim(self.tmp.name, self.clock, self.http, env={"XAI_API_KEY": KEY}, mode="qa")
        self.sim.start_app().shutdown()
        path = settings_file.settings_path(self.tmp.name)
        data = json.loads(path.read_text())
        data["connection"]["paths"]["audio"] = "Custom/Sounds/Mine"
        path.write_text(json.dumps(data))
        self.app = self.sim.start_app()
        self.plugin = FakePlugin(self.root, self.clock, mode="qa")
        self.plugin.ui["connection"]["paths"]["audio"] = "Custom/Sounds/Mine"
        self.plugin.unloadable = ("Custom/",)
        self.plugin.start()
        self.sim.run(self.plugin, 3)
        self.plugin.request_test_tone()
        self.sim.run(self.plugin, 3)
        self.assertEqual(len(self.speaks()), 1)
        self.assertIn("is fixed", self.plugin.audio_out["note"])


class RealtimeFallbackTests(RealtimeSim):
    def test_silent_realtime_falls_back_to_the_chain(self):
        http = FakeHttp()
        http.route("/responses", lambda r: FakeResponse(text_stream(["Hallo zurück."]), "text/event-stream"))
        http.route("/tts", lambda r: FakeResponse(pcm(0.5), "audio/pcm"))
        self.start(mode="auto", http=http)
        self.connect()
        conn = self.server.conn
        conn.send({"type": "input_audio_buffer.speech_started", "item_id": "u1", "audio_start_ms": 0})
        conn.send({"type": "input_audio_buffer.speech_stopped", "item_id": "u1", "audio_end_ms": 900})
        self.assertTrue(self.pump(lambda: bool(self.app.realtime_off), timeout=10), self.app.mode_note)
        self.assertEqual(self.app.active_mode, "chain")
        self.assertIn("Realtime off", self.app.mode_note)
        self.assertTrue(self.pump(lambda: "Realtime did not respond" in self.plugin.turn))
        # typed text is answered by the chain with xai (the menus still say echo / tone)
        self.app.handle_user_text("Hallo")
        self.assertTrue(self.pump(lambda: bool(self.speaks())))
        self.assertEqual(self.speaks()[0]["text"], "Hallo zurück.")
        # API Reconnect gives realtime a new chance
        self.app.reconnect_api()
        self.assertEqual(self.app.realtime_off, "")
        self.assertTrue(self.pump(lambda: self.app.active_mode == "realtime"), self.app.mode_note)


if __name__ == "__main__":
    unittest.main()
