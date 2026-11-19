"""Realtime mode (Grok Voice over WebSocket), mode selection, proactive timer and time context.

Everything runs against tests/fake_ws.py (a local fake of the realtime server) and the fake plugin
on the file channel; no key, no network. Event names and payloads follow docs.x.ai (17.11.2026);
TODO(verify) against the real server.
"""
from __future__ import annotations

import json
import math
import struct
import tempfile
import time
import unittest
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from aibody_companion import settings_file
from aibody_companion.pipeline.context import (
    format_since,
    is_silent,
    nudge_text,
    time_context,
)
from aibody_companion.pipeline.realtime import SegmentAssembler, resample_pcm16
from aibody_companion.proactive import ProactiveTimer
from aibody_companion.realtime_voice import RealtimeVoice
from tests.fake_ws import FakeRealtimeServer
from tests.fakes import FakeClock, FakeHttp, FakePlugin, FakeResponse, text_stream
from tests.test_e2e_simulation import Sim

KEY = "xai-FAKE-NOT-A-KEY"
BERLIN = timezone(timedelta(hours=1))
NOW = datetime(2026, 11, 17, 18, 55, tzinfo=BERLIN)


def tone(seconds: float, rate: int = 24000, amp: int = 8000) -> bytes:
    n = int(seconds * rate)
    return struct.pack(f"<{n}h", *(int(amp * math.sin(i / 8)) for i in range(n)))


def speech_frame(ms: int = 30, rate: int = 16000) -> bytes:
    n = rate * ms // 1000
    return struct.pack(f"<{n}h", *(int(6000 * math.sin(i / 3)) for i in range(n)))


class UnitTests(unittest.TestCase):
    def test_segments_start_early_and_follow_sentences(self):
        a = SegmentAssembler(24000, first_s=1.0, min_s=2.0, max_s=6.0)
        self.assertEqual(a.feed_audio(tone(0.5)), [])
        self.assertEqual(a.feed_text("Hallo! "), [], "a sentence end alone is not enough audio yet")
        segs = a.feed_audio(tone(0.6))
        self.assertEqual(len(segs), 1)
        self.assertAlmostEqual(len(segs[0][0]) / 2 / 24000, 1.1, places=2)
        self.assertEqual(segs[0][1], "Hallo!")
        self.assertEqual(a.feed_text("Wie geht es dir? "), [])  # no audio buffered yet
        self.assertEqual(a.feed_audio(tone(1.0)), [], "later segments need min_s")
        segs = a.feed_audio(tone(1.2))
        self.assertEqual([s[1] for s in segs], ["Wie geht es dir?"])
        a.feed_text("Und")
        a.feed_audio(tone(0.3))
        rest = a.finish()
        self.assertEqual(rest[0][1], "Und")
        self.assertEqual(a.transcript, "Hallo! Wie geht es dir? Und")

    def test_long_audio_without_sentence_end_is_cut_at_a_quiet_spot(self):
        a = SegmentAssembler(24000, first_s=1.0, min_s=2.0, max_s=3.0)
        loud, quiet = tone(2.5), bytes(2 * 2400)  # 100 ms of silence at 2.5 s
        segs = a.feed_audio(loud + quiet + tone(1.0))
        self.assertEqual(len(segs), 1)
        cut_s = len(segs[0][0]) / 2 / 24000
        self.assertGreaterEqual(cut_s, 2.5)
        self.assertLessEqual(cut_s, 2.6)

    def test_resample(self):
        pcm = tone(0.1, 16000)
        out = resample_pcm16(pcm, 16000, 24000)
        self.assertEqual(len(out) // 2, 2400)
        self.assertEqual(resample_pcm16(pcm, 16000, 16000), pcm)

    def test_time_context_and_silence(self):
        ctx = time_context(NOW, 185)
        self.assertIn("Tuesday, 17 November 2026, 18:55 (UTC+01:00)", ctx)
        self.assertIn("3 minutes ago", ctx)
        self.assertIn("no clock", ctx)
        self.assertIn("start of the conversation", format_since(None))
        self.assertIn("Tuesday", nudge_text("", NOW, None))
        for s in ("[silent]", "Silent.", "", "  [SILENT] ", "schweigen"):
            self.assertTrue(is_silent(s), s)
        self.assertFalse(is_silent("Na, so still heute?"))

    def test_proactive_timer_waits_and_backs_off(self):
        clock = FakeClock()
        p = ProactiveTimer(True, 60, clock)
        clock.advance(59)
        self.assertFalse(p.due(True))
        clock.advance(2)
        self.assertFalse(p.due(False), "not while someone talks / the body speaks")
        self.assertTrue(p.due(True))
        p.fired()
        clock.advance(61)
        self.assertFalse(p.due(True), "second nudge in a row waits twice as long")
        clock.advance(60)
        self.assertTrue(p.due(True))
        p.fired()
        p.user_activity()
        clock.advance(61)
        self.assertTrue(p.due(True), "user speech resets the backoff")
        p.configure(False, 60)
        self.assertFalse(p.due(True))

    def test_idle_zero_switches_the_nudges_off(self):
        """Leon, 19.11.2026: slider "Proactive idle (s)" at 0 = off. Never a nudge on every tick."""
        for idle in (0, 0.0, 0.5, -3):
            clock = FakeClock()
            p = ProactiveTimer(True, idle, clock)
            self.assertFalse(p.active, idle)
            for _ in range(3):
                self.assertFalse(p.due(True), idle)
                clock.advance(100000)
            self.assertFalse(p.due(True), f"not even after a very long idle (idle_seconds={idle})")
        clock = FakeClock()
        p = ProactiveTimer(True, 60, clock)
        self.assertTrue(p.active)
        p.configure(True, 0)
        clock.advance(10000)
        self.assertFalse(p.active)
        self.assertFalse(p.due(True))
        p.configure(True, 30)  # back from 0: counts from now, no instant nudge
        self.assertTrue(p.active)
        self.assertFalse(p.due(True))
        clock.advance(31)
        self.assertTrue(p.due(True))

    def test_idle_range_allows_zero(self):
        from aibody_companion import settings_file

        self.assertEqual(settings_file.RANGES[("ai", "proactive", "idle_seconds")][0], 0.0)
        data, errors = settings_file.validate({"ai": {"proactive": {"idle_seconds": 0}}})
        self.assertEqual(errors, [])
        self.assertEqual(data["ai"]["proactive"]["idle_seconds"], 0.0)
        data, _ = settings_file.validate({"ai": {"proactive": {"idle_seconds": -5}}})
        self.assertEqual(data["ai"]["proactive"]["idle_seconds"], 0.0, "negative values clamp to 0 = off")


class RealtimeSim(unittest.TestCase):
    """Companion in realtime mode against the fake server, fake plugin on the file channel."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.server = FakeRealtimeServer()
        patcher = mock.patch.object(RealtimeVoice, "BACKOFF", (0.05, 0.1))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.wall = [NOW]

    def tearDown(self):
        if getattr(self, "app", None):
            self.app.shutdown()
        self.server.stop()
        self.tmp.cleanup()

    def connector(self, url, headers, timeout):
        from aibody_companion.pipeline.websocket import WebSocket

        self.urls = getattr(self, "urls", []) + [url]
        local = url.replace("wss://api.x.ai/v1/realtime", f"ws://127.0.0.1:{self.server.port}/v1/realtime")
        return WebSocket.connect(local, headers, timeout)

    def start(self, mode="auto", env=None, ai=None, http=None):
        self.sim = Sim(self.tmp.name, self.clock, http, env={"XAI_API_KEY": KEY} if env is None else env,
                       background=True, mode=mode, connector=self.connector, wall=lambda: self.wall[0])
        if ai:
            self.sim.start_app().shutdown()
            path = settings_file.settings_path(self.tmp.name)
            data = json.loads(path.read_text())
            for k, v in ai.items():
                if isinstance(v, dict):
                    data["ai"].setdefault(k, {}).update(v)
                else:
                    data["ai"][k] = v
            path.write_text(json.dumps(data))
        self.app = self.sim.start_app()
        self.plugin = FakePlugin(Path(self.tmp.name), self.clock, mode=mode)
        for section, values in (ai or {}).items():
            if section in self.plugin.ai_ui and isinstance(values, dict):
                self.plugin.ai_ui[section].update(values)
        self.plugin.start()
        return self.app

    def pump(self, until=None, timeout=3.0, dt=0.05):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.sim.run(self.plugin, dt, dt=dt)
            if until is not None and until():
                return True
            time.sleep(0.005)
        return until is None

    def connect(self):
        self.assertTrue(self.pump(lambda: self.app.active_mode == "realtime"), self.app.mode_note)
        self.pump(lambda: bool(self.plugin.app_alive))

    def speaks(self):
        return self.sim.sent(self.plugin, "speak")


class RealtimeSessionTests(RealtimeSim):
    def test_session_setup(self):
        self.start()
        self.connect()
        conn = self.server.conn
        self.assertEqual(conn.headers["authorization"], f"Bearer {KEY}")
        self.assertIn("model=grok-voice-latest", conn.path)
        update = conn.received[0]
        self.assertEqual(update["type"], "session.update")
        s = update["session"]
        self.assertEqual(s["voice"], "eve")
        self.assertEqual(s["turn_detection"], {"type": "server_vad"})
        self.assertEqual(s["audio"]["input"]["format"], {"type": "audio/pcm", "rate": 16000})
        self.assertEqual(s["audio"]["output"]["format"], {"type": "audio/pcm", "rate": 24000})
        self.assertIn("friendly, curious character", s["instructions"])  # persona
        self.assertIn("Tuesday, 17 November 2026, 18:55", s["instructions"])  # time context
        self.assertIn("no clock of your own", s["instructions"])
        tool = s["tools"][0]
        self.assertEqual(tool["name"], "express")
        self.assertIn("happy", tool["parameters"]["properties"]["expression"]["enum"])
        self.assertEqual(self.app.mode_info()["active"], "realtime")
        hb = self.sim.sent(self.plugin, "companion_heartbeat")[-1]
        self.assertEqual(hb["mode"]["requested"], "auto")

    def test_mic_audio_streams_and_is_muted_while_the_body_speaks(self):
        self.start()
        self.connect()
        frame = speech_frame()
        for _ in range(5):
            self.app.handle_audio_frame(frame)
        self.assertTrue(self.server.wait(lambda: len(self.server.appended_audio()) >= 5 * len(frame)))
        self.assertEqual(self.server.appended_audio()[: len(frame)], frame)
        # The body talks -> the mic sends silence (no echo cancellation)
        self.server.respond(["Hallo! "], tone(1.5))
        self.assertTrue(self.pump(lambda: bool(self.speaks())))
        self.assertFalse(self.app.gate.is_open)
        before = len(self.server.appended_audio())
        self.app.handle_audio_frame(frame)
        self.assertTrue(self.server.wait(lambda: len(self.server.appended_audio()) > before))
        self.assertEqual(self.server.appended_audio()[before:], bytes(len(frame)))

    def test_answer_is_cut_into_segments_and_spoken_from_the_first(self):
        self.start()
        self.connect()
        self.server.respond(["Hallo! ", "Schön, dass du da bist. ", "Wie war dein Tag?"], tone(5.0),
                            call={"name": "express", "arguments": {"expression": "happy", "gesture": "nod"}})
        self.assertTrue(self.pump(lambda: self.app.realtime.response_id is None
                                  and sum(s["duration"] for s in self.speaks()) > 4.99))
        speaks = self.speaks()
        self.assertEqual(speaks[0]["text"], "Hallo!")
        total = 0.0
        for s in speaks:
            with wave.open(str(Path(self.tmp.name) / s["audio"]), "rb") as w:
                self.assertEqual((w.getframerate(), w.getsampwidth(), w.getnchannels()), (24000, 2, 1))
                self.assertAlmostEqual(w.getnframes() / 24000, s["duration"], places=2)
                total += s["duration"]
        self.assertAlmostEqual(total, 5.0, places=2)
        self.assertLess(speaks[0]["duration"], 2.0, "speech starts on a short first segment")
        # express -> existing commands; result back without response.create (no second answer)
        self.assertEqual(self.sim.sent(self.plugin, "expression")[0]["name"], "happy")
        self.assertEqual(self.sim.sent(self.plugin, "gesture")[0]["name"], "nod")
        self.assertTrue(self.server.wait_type("conversation.item.create"))
        out = [e for e in self.server.conn.received if e["type"] == "conversation.item.create"][-1]
        self.assertEqual(out["item"]["type"], "function_call_output")
        self.assertEqual(out["item"]["call_id"], "call-1")
        self.assertNotIn("response.create", self.server.conn.types())
        self.assertEqual(self.app.history[-1]["content"], "Hallo! Schön, dass du da bist. Wie war dein Tag?")

    def test_barge_in_stops_the_body_and_drops_the_rest(self):
        self.start()
        self.connect()
        c = self.server.conn
        c.send({"type": "response.created", "response": {"id": "r1"}})
        c.send({"type": "response.output_audio_transcript.delta", "response_id": "r1", "delta": "Das ist eine lange "
                "Geschichte. "})
        c.send({"type": "response.output_audio.delta", "response_id": "r1",
                "delta": __import__("base64").b64encode(tone(2.0)).decode()})
        self.assertTrue(self.pump(lambda: len(self.speaks()) == 1))
        self.assertTrue(self.plugin.playing)
        c.send({"type": "input_audio_buffer.speech_started", "item_id": "u1", "audio_start_ms": 100})
        self.assertTrue(self.pump(lambda: bool(self.sim.sent(self.plugin, "stop_speaking"))))
        self.assertFalse(self.plugin.playing)
        # late audio of the interrupted answer is ignored
        c.send({"type": "response.output_audio.delta", "response_id": "r1",
                "delta": __import__("base64").b64encode(tone(3.0)).decode()})
        c.send({"type": "response.done", "response": {"id": "r1"}})
        self.pump(timeout=0.3)
        self.assertEqual(len(self.speaks()), 1)
        # time context refreshed for the new user turn
        self.assertTrue(self.server.wait_type("session.update", 2))
        # push-to-talk barge-in also sends response.cancel
        self.app.mic_settings = self.app.mic_settings.__class__(mode="ptt")
        self.app.input.apply(self.app.mic_settings)
        self.server.respond(["Noch was. "], tone(2.0), response_id="r2")
        self.assertTrue(self.pump(lambda: len(self.speaks()) >= 2 and self.app.realtime.response_id is None))
        c.send({"type": "response.created", "response": {"id": "r3"}})
        self.pump(timeout=0.2)
        self.app.handle_ptt(True)
        self.assertTrue(self.server.wait_type("response.cancel"))

    def test_reconnects_after_a_drop(self):
        self.start()
        self.connect()
        self.server.conn.drop()
        self.assertTrue(self.pump(lambda: self.app.active_mode == "chain", timeout=2))
        self.assertTrue(self.pump(lambda: len(self.server.connections) == 2 and self.app.active_mode == "realtime",
                                  timeout=3), self.app.mode_note)
        self.assertEqual(self.server.connections[1].received[0]["type"], "session.update")

    def test_refused_connection_falls_back_to_chain_and_reports_it(self):
        self.server.stop()
        self.server = FakeRealtimeServer(refuse_status=401)
        self.start()
        self.assertTrue(self.pump(lambda: self.server.attempts >= 2, timeout=3))
        self.assertEqual(self.app.active_mode, "chain")
        self.assertIn("API key rejected", self.app.mode_note)
        self.assertIn("falling back to the chain", self.app.mode_note)
        self.assertEqual(self.app.engine_set.key_info()["xai"]["state"], "rejected", "key status in the AI tab")
        # mic frames go to the local VAD meanwhile
        for _ in range(3):
            self.assertIsNone(self.app.handle_audio_frame(speech_frame()))
        self.assertTrue(self.app.input.segmenter.in_speech)


class ModeSelectionTests(RealtimeSim):
    def test_auto_without_key_is_chain(self):
        self.start(env={})
        self.pump(timeout=0.2)
        self.assertEqual(self.app.active_mode, "chain")
        self.assertIsNone(self.app.realtime)
        self.assertIn("no xAI API key", self.app.mode_note)

    def test_auto_with_elevenlabs_is_chain(self):
        app = self.start()
        app.apply_engines({"tts": "elevenlabs"})
        app._update_mode()
        self.assertIsNone(app.realtime)
        self.assertIn("elevenlabs", app.mode_note)

    def test_chain_and_realtime_without_key(self):
        app = self.start(mode="chain")
        self.assertIsNone(app.realtime)
        self.assertEqual(app.apply_ai({"mode": "realtime"}), [])
        self.assertIsNotNone(app.realtime, "switched live from the plugin")
        self.assertEqual(app.apply_ai({"mode": "bogus"})[0], "ai.mode: must be one of qa, auto, realtime, chain")
        app.shutdown()
        self.app = self.start(mode="realtime", env={})
        self.assertIn("Realtime not configured", self.app.mode_note)


class ProactiveTests(RealtimeSim):
    def test_realtime_nudge_after_silence_and_silent_answer_is_dropped(self):
        self.start(ai={"proactive": {"idle_seconds": 30}})
        self.connect()
        self.wall[0] = NOW + timedelta(minutes=2)
        self.sim.run(self.plugin, 29)
        self.assertNotIn("response.create", self.server.conn.types())
        self.assertTrue(self.pump(lambda: "response.create" in self.server.conn.types(), dt=0.5))
        item = [e for e in self.server.conn.received if e["type"] == "conversation.item.create"][-1]["item"]
        text = item["content"][0]["text"]
        self.assertEqual(item["role"], "user")
        self.assertIn("[App context", text)
        self.assertIn("18:57", text)
        self.assertIn("[silent]", text)
        # the AI stays silent -> nothing is played
        self.server.respond(["[silent]"], tone(0.6), response_id="n1")
        self.pump(timeout=0.5)
        self.assertEqual(self.speaks(), [])
        # next nudge waits twice as long; a real answer is spoken
        self.sim.run(self.plugin, 59)
        self.assertEqual(self.server.conn.types().count("response.create"), 1)
        self.assertTrue(self.pump(lambda: self.server.conn.types().count("response.create") == 2, dt=0.5))
        self.server.respond(["Na, so ruhig heute? ", "Erzähl doch mal."], tone(2.5), response_id="n2")
        self.assertTrue(self.pump(lambda: len(self.speaks()) >= 1))
        self.assertEqual(self.speaks()[0]["text"], "Na, so ruhig heute?")

    def test_no_nudge_while_the_user_speaks_or_when_disabled(self):
        self.start(ai={"proactive": {"idle_seconds": 30}})
        self.connect()
        self.server.conn.send({"type": "input_audio_buffer.speech_started"})
        self.pump(timeout=0.2)
        self.sim.run(self.plugin, 40)
        self.assertNotIn("response.create", self.server.conn.types())
        self.server.conn.send({"type": "input_audio_buffer.speech_stopped"})
        self.pump(timeout=0.2)
        self.app.apply_ai({"proactive": {"enabled": "false"}})  # VaM sends booleans as text
        self.sim.run(self.plugin, 100)
        self.assertNotIn("response.create", self.server.conn.types())
        self.assertFalse(self.sim.sent(self.plugin, "companion_heartbeat")[-1]["proactive"]["enabled"])

    def test_idle_zero_never_nudges_in_realtime_after_a_long_silence(self):
        self.start(ai={"proactive": {"idle_seconds": 0}})
        self.connect()
        self.wall[0] = NOW + timedelta(hours=3)
        self.sim.run(self.plugin, 600)
        self.assertNotIn("response.create", self.server.conn.types())
        beat = self.sim.sent(self.plugin, "companion_heartbeat")[-1]["proactive"]
        self.assertEqual(beat["idle_seconds"], 0)
        self.assertNotIn("status", beat)
        # live: the slider dragged to 0 while a nudge was due
        self.app.apply_ai({"proactive": {"idle_seconds": 30}})
        self.app.apply_ai({"proactive": {"idle_seconds": 0}})
        self.sim.run(self.plugin, 600)
        self.assertNotIn("response.create", self.server.conn.types())

    def test_idle_zero_never_nudges_in_the_chain_path(self):
        http = FakeHttp()
        http.route("/responses", lambda r: FakeResponse(text_stream(["Hey?"], "resp-1"), "text/event-stream"))
        http.route("/tts", lambda r: FakeResponse(b"\x01\x00" * 24000, "audio/pcm"))
        self.start(mode="chain", http=http, ai={"proactive": {"idle_seconds": 0}})
        self.plugin.ui["engines"] = {"stt": "null", "llm": "xai", "tts": "xai"}
        self.pump(lambda: bool(self.plugin.app_alive))
        self.sim.run(self.plugin, 1000)
        self.assertTrue(self.app.wait_turns())
        self.assertEqual([r for r in http.requests if r.full_url.endswith("/responses")], [])
        self.assertEqual(self.speaks(), [])

    def test_chain_nudge_and_time_context(self):
        http = FakeHttp()
        answers = [text_stream(["Gut, danke."], "resp-1"), text_stream(["[silent]"], "resp-2"),
                   text_stream(["Hey, bist du noch da?"], "resp-3")]
        http.route("/responses", lambda r: FakeResponse(answers.pop(0), "text/event-stream"))
        http.route("/tts", lambda r: FakeResponse(b"\x01\x00" * 24000, "audio/pcm"))
        self.start(mode="chain", http=http, ai={"proactive": {"idle_seconds": 30}})
        self.plugin.ui["engines"] = {"stt": "null", "llm": "xai", "tts": "xai"}
        self.pump(lambda: bool(self.plugin.app_alive))
        self.app.handle_user_text("Wie geht's?")
        self.assertTrue(self.app.wait_turns())
        first = json.loads(http.requests[0].data)
        self.assertIn("it is now Tuesday, 17 November 2026, 18:55", first["input"][0]["content"])
        self.assertTrue(first["input"][0]["content"].endswith("Wie geht's?"))
        self.assertEqual(self.app.history[0]["content"], "Wie geht's?", "history keeps the plain text")
        self.sim.run(self.plugin, 5)  # the answer is played
        self.sim.run(self.plugin, 31)
        self.assertTrue(self.app.wait_turns())
        llm = [json.loads(r.data) for r in http.requests if r.full_url.endswith("/responses")]
        self.assertEqual(len(llm), 2)
        self.assertIn("[App note:", llm[1]["input"][0]["content"])
        self.assertIn("Last exchange:", llm[1]["input"][0]["content"])
        self.sim.run(self.plugin, 1)
        self.assertEqual(len(self.speaks()), 1, "a [silent] answer is not spoken")
        self.sim.run(self.plugin, 61)
        self.assertTrue(self.app.wait_turns())
        self.sim.run(self.plugin, 1)
        self.assertEqual(self.speaks()[-1]["text"], "Hey, bist du noch da?")
        self.assertEqual([h["role"] for h in self.app.history], ["user", "assistant", "assistant"])


if __name__ == "__main__":
    unittest.main()
