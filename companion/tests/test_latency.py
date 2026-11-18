"""Latency metric: end of speech -> first sound, with breakdown, in the log and the heartbeat."""
from __future__ import annotations

import io
import json
import unittest

from aibody_companion import logsetup
from aibody_companion.latency import LatencyStats, LatencyTrace, describe
from tests.fakes import FakeResponse, text_stream
from tests.test_qa_flow import QaFlowTests, pcm
from tests.test_realtime import RealtimeSim, tone


class UnitTests(unittest.TestCase):
    def test_parts_add_up_and_stats_average(self):
        t = LatencyTrace(10.0, "chain")
        for step, at in [("stt", 10.8), ("llm_first_token", 11.3), ("first_sentence", 11.5), ("tts", 11.9),
                         ("write", 11.92), ("speak_sent", 12.0)]:
            t.mark(step, at)
        result = t.finish(12.4)
        self.assertEqual(result["total_s"], 2.4)
        self.assertAlmostEqual(sum(result["parts"].values()), 2.4, places=3)
        self.assertEqual(result["parts"]["stt"], 0.8)
        self.assertEqual(result["parts"]["play"], 0.4)
        self.assertIsNone(t.finish(13.0), "only the first sound counts")
        self.assertIn("STT 0.80", describe(result))
        stats = LatencyStats()
        stats.add(result)
        stats.add({"kind": "chain", "total_s": 1.6, "parts": {"stt": 1.6}})
        self.assertEqual(stats.info()["avg_s"], 2.0)
        self.assertEqual(stats.info()["last_s"], 1.6)
        self.assertEqual(stats.info()["n"], 2)

    def test_out_of_order_marks_never_go_negative(self):
        t = LatencyTrace(5.0, "chain")
        t.mark("write", 5.5)
        t.mark("tts", 5.49)
        t.mark("first_sentence", 5.6)  # a mark after a later step (clock granularity)
        self.assertTrue(all(v >= 0 for v in t.finish(6.0)["parts"].values()))


class ChainLatencyTests(QaFlowTests):
    """QaFlow simulation where each service takes time on the fake clock."""

    for _name in [n for n in dir(QaFlowTests) if n.startswith("test_")]:
        locals()[_name] = None
    del _name

    def setUp(self):
        super().setUp()

        def stt(r):
            self.clock.advance(0.8)
            return FakeResponse(json.dumps({"text": "Wie spät ist es?"}).encode())

        def llm(r):
            self.clock.advance(0.5)
            return FakeResponse(text_stream(["Es ist sieben. ", "Noch etwas?"]), "text/event-stream")

        def tts(r):
            self.clock.advance(0.3)
            return FakeResponse(pcm(0.8), "audio/pcm")

        self.http.route("/stt", stt)
        self.http.route("/responses", llm)
        self.http.route("/tts", tts)
        self.stream = io.StringIO()
        logsetup.setup(None, stream=self.stream)
        self.addCleanup(logsetup.teardown)

    def latency(self):
        beats = [b for b in self.sim.sent(self.plugin, "companion_heartbeat") if b.get("latency")]
        return beats[-1]["latency"] if beats else None

    def test_spoken_turn(self):
        self.start()
        self.assertIsNone(self.latency())
        self.speak_mic_question()
        self.sim.run(self.plugin, 2)
        lat = self.latency()
        self.assertIsNotNone(lat, "heartbeat carries the latency after the first sound")
        self.assertEqual(lat["n"], 1)
        self.assertEqual(lat["kind"], "chain")
        self.assertGreaterEqual(lat["last_s"], 1.6, "STT 0.8 + LLM 0.5 + TTS 0.3 at least")
        self.assertEqual(list(lat["parts"])[:4], ["STT", "LLM first token", "first sentence", "TTS"])
        self.assertAlmostEqual(lat["parts"]["STT"], 0.8, places=2)
        self.assertAlmostEqual(lat["parts"]["LLM first token"], 0.5, places=2)
        self.assertIn("plugin start", lat["parts"])
        self.assertAlmostEqual(sum(lat["parts"].values()), lat["last_s"], places=2)
        self.assertIn("Latency t", self.stream.getvalue(), "one INFO line per turn, also without verbose")

    def test_typed_turn_has_no_stt_part_and_average_is_rolling(self):
        self.start()
        self.app.handle_user_text("Hallo")
        self.sim.run(self.plugin, 3)
        self.app.handle_user_text("Noch mal")
        self.sim.run(self.plugin, 3)
        lat = self.latency()
        self.assertEqual(lat["n"], 2)
        self.assertNotIn("STT", lat["parts"])
        self.assertGreaterEqual(lat["avg_s"], 0.8)


class RealtimeLatencyTests(RealtimeSim):
    def test_realtime_turn(self):
        self.start()
        self.connect()
        self.server.conn.send({"type": "input_audio_buffer.speech_started"})
        self.server.conn.send({"type": "input_audio_buffer.speech_stopped"})
        self.pump(lambda: self.app.realtime.turn is not None and self.app.realtime.turn.latency is not None)
        self.server.respond(["Hallo! ", "Wie geht's?"], tone(3.0))
        self.assertTrue(self.pump(lambda: self.app.latency.info() is not None))
        info = self.app.latency.info()
        self.assertEqual(info["kind"], "realtime")
        self.assertIn("server first audio", info["parts"])
        self.assertIn("plugin start", info["parts"])


del QaFlowTests, RealtimeSim
