"""Version 29: Silero voice detector (onnxruntime, no torch) and voice barge-in by a loudness rule."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from aibody_companion import settings_file
from aibody_companion.audio import BargeInRule, EchoGate, InputProcessor, MicSettings, silero_model_path
from aibody_companion.audio.silero import CHUNK, SileroVad
from aibody_companion.audio.vad import make_vad
from aibody_companion.config import Config
from aibody_companion.orchestrator import Companion
from aibody_companion.pipeline import EchoLlm, ToneTts
from tests.fakes import FakeClock
from tests.test_routing import FakeTransport
from tests.test_vad_engines import HeardStt, tone, wobbly

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

REAL_MODEL = os.environ.get("AIBODY_SILERO_MODEL") or "/tmp/silero_vad.onnx"


class FakeSession:
    """Stands in for an onnxruntime InferenceSession of silero_vad.onnx (version 5)."""

    def __init__(self, probabilities=None, names=("input", "state", "sr")):
        self.probabilities = list(probabilities or [])
        self.names = names
        self.calls = []
        self.fail = False

    def get_inputs(self):
        return [type("I", (), {"name": n})() for n in self.names]

    def run(self, _outputs, feeds):
        if self.fail:
            raise RuntimeError("boom")
        self.calls.append({k: (v.shape, v.dtype) for k, v in feeds.items()})
        p = self.probabilities.pop(0) if self.probabilities else 0.0
        return np.array([[p]], dtype=np.float32), feeds["state"] + 0.0


class FakeOrt:
    def __init__(self, session):
        self.session = session

    class SessionOptions:
        pass

    def InferenceSession(self, path, sess_options=None, providers=None):  # noqa: N802 - onnxruntime's name
        self.providers = providers
        return self.session


def importer_for(session):
    def importer(name):
        if name == "onnxruntime":
            return FakeOrt(session)
        if name == "numpy":
            return np
        raise ImportError(name)
    return importer


@unittest.skipIf(np is None, "numpy is not installed")
class SileroTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.model = str(Path(self.tmp.name) / "silero_vad.onnx")
        Path(self.model).write_bytes(b"not a real model")

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_model_and_missing_onnxruntime_have_plain_notes(self):
        vad, info = make_vad("silero", 2, 0.01, silero_model=str(Path(self.tmp.name) / "none.onnx"))
        self.assertEqual(info.name, "energy")
        self.assertIn("silero model not found", info.note)
        self.assertIn("github.com/snakers4/silero-vad", info.note)

        def missing(name):
            raise ImportError(name)
        _, info = make_vad("silero", 2, 0.01, importer=missing, silero_model=self.model)
        self.assertIn("python -m pip install onnxruntime", info.note)
        _, info = make_vad("silero", 2, 0.01)
        self.assertIn("no model path", info.note)

    def test_auto_stays_quiet_without_the_model_and_uses_it_with_the_model(self):
        _, info = make_vad("auto", 2, 0.01, silero_model=str(Path(self.tmp.name) / "none.onnx"), importer=lambda n: (_ for _ in ()).throw(ImportError(n)))
        self.assertEqual((info.name, info.note), ("energy", ""))
        vad, info = make_vad("auto", 2, 0.01, importer=importer_for(FakeSession()), silero_model=self.model)
        self.assertEqual((info.name, vad.name), ("silero", "silero"))
        self.assertIn("strictness 2", info.text)

    def test_wrong_model_version_is_refused(self):
        _, info = make_vad("silero", 2, 0.01, importer=importer_for(FakeSession(names=("input", "h", "c", "sr"))), silero_model=self.model)
        self.assertEqual(info.name, "energy")
        self.assertIn("version 5", info.note)

    def test_other_sample_rates_fall_back(self):
        _, info = make_vad("silero", 2, 0.01, sample_rate=24000, importer=importer_for(FakeSession()), silero_model=self.model)
        self.assertIn("16 kHz", info.note)

    def test_frames_are_collected_into_chunks_and_decide_with_hangover(self):
        session = FakeSession()
        vad, _ = make_vad("silero", 2, 0.001, importer=importer_for(session), silero_model=self.model)
        session.calls.clear()
        session.probabilities = [0.9, 0.9, 0.1, 0.1, 0.1, 0.1, 0.1]
        frame = tone(0.1)  # 480 samples = 30 ms
        results = [vad.decide(frame, 0.1) for _ in range(8)]
        self.assertEqual(len(session.calls), (8 * 480) // CHUNK, "a model run per full chunk of 512 samples")
        shapes = session.calls[0]
        self.assertEqual(shapes["input"][0], (1, 64 + CHUNK), "64 samples of context + the chunk")
        self.assertEqual(shapes["state"][0], (2, 1, 128))
        self.assertTrue(results[1], "probability 0.9 above the threshold 0.5")
        self.assertTrue(results[2] and results[3] and results[4], "hangover of 3 frames")
        self.assertFalse(results[7])

    def test_quiet_frames_never_count_even_with_a_high_probability(self):
        session = FakeSession([0.99] * 20)
        vad, _ = make_vad("silero", 2, 0.05, importer=importer_for(session), silero_model=self.model)
        self.assertFalse(any(vad.decide(tone(0.001), 0.001) for _ in range(6)))

    def test_strictness_changes_the_threshold(self):
        loose = make_vad("silero", 0, 0.001, importer=importer_for(FakeSession()), silero_model=self.model)[0]
        strict = make_vad("silero", 3, 0.001, importer=importer_for(FakeSession()), silero_model=self.model)[0]
        self.assertLess(loose.threshold, strict.threshold)

    def test_hold_forgets_the_stream_and_a_broken_session_falls_back_once(self):
        session = FakeSession([0.9] * 10)
        vad, _ = make_vad("silero", 2, 0.001, importer=importer_for(session), silero_model=self.model)
        vad.decide(tone(0.1), 0.1)
        vad.decide(tone(0.1), 0.1)
        self.assertEqual(len(vad._pending), 2 * 480 - CHUNK)
        vad.hold()
        self.assertEqual(vad._pending, [])
        session.fail = True
        with self.assertLogs("aibody_companion.audio.silero", "WARNING") as logs:
            for _ in range(4):
                vad.decide(tone(0.1), 0.1)
        self.assertEqual(len(logs.output), 1, "warned once")

    def test_model_path_from_environment_or_the_models_folder(self):
        self.assertEqual(silero_model_path("D:/VaM", {"AIBODY_SILERO_MODEL": "X/y.onnx"}), "X/y.onnx")
        path = silero_model_path("D:/VaM", {})
        self.assertTrue(path.replace("\\", "/").endswith("Saves/PluginData/AIBody/models/silero_vad.onnx"))

    def test_input_processor_uses_it(self):
        s = MicSettings(vad_engine="silero")
        ip = InputProcessor(s, EchoGate(), silero_model=self.model)
        self.assertEqual(ip.vad_info.name, "energy", "no onnxruntime session for the fake file: refused, plain note")
        self.assertTrue(ip.vad_info.note)


@unittest.skipUnless(np is not None and os.path.isfile(REAL_MODEL), "needs numpy, onnxruntime and silero_vad.onnx (AIBODY_SILERO_MODEL)")
class RealModelTests(unittest.TestCase):
    def test_the_real_model_runs_and_calls_noise_non_speech(self):
        import random
        vad, info = make_vad("silero", 2, 0.001, silero_model=REAL_MODEL)
        self.assertEqual(info.name, "silero", info.note)
        rnd = random.Random(1)
        noise = b"".join(int(rnd.gauss(0, 300)).to_bytes(2, "little", signed=True) for _ in range(480))
        self.assertFalse(any(vad.decide(noise, 0.01) for _ in range(30)))
        self.assertLess(vad.probability, 0.5)


class BargeRuleTests(unittest.TestCase):
    FRAME = b"\x00\x00" * 480

    def run_rule(self, rule, levels, speaking=True):
        out = None
        for rms in levels:
            out = rule.push(self.FRAME, rms, speaking) or out
        return out

    def test_a_clearly_louder_stretch_fires_and_returns_its_frames(self):
        rule = BargeInRule(ratio=2.0, min_ms=600, frame_ms=30, floor=0.02)
        self.assertIsNone(self.run_rule(rule, [0.03] * 40), "the echo alone, however long")
        self.assertIsNotNone(rule.echo)
        frames = self.run_rule(rule, [0.1] * 25)
        self.assertTrue(frames)
        self.assertGreaterEqual(len(frames), 20)
        self.assertEqual(rule._loud, 0, "reset after firing")

    def test_a_short_burst_does_not_fire(self):
        rule = BargeInRule(ratio=2.0, min_ms=600, frame_ms=30, floor=0.02)
        self.run_rule(rule, [0.03] * 40)
        self.assertIsNone(self.run_rule(rule, [0.2] * 8 + [0.03] * 40))

    def test_nothing_while_the_body_is_not_playing_or_while_warming_up(self):
        rule = BargeInRule(ratio=2.0, min_ms=300, frame_ms=30, floor=0.02)
        self.assertIsNone(self.run_rule(rule, [0.5] * 40, speaking=False))
        rule = BargeInRule(ratio=2.0, min_ms=300, frame_ms=30, floor=0.02, warmup_ms=900)
        self.assertIsNone(self.run_rule(rule, [0.5] * 10), "the first frames only teach (echo ramps up)")

    def test_below_the_floor_is_never_a_user(self):
        rule = BargeInRule(ratio=2.0, min_ms=300, frame_ms=30, floor=0.05)
        self.assertIsNone(self.run_rule(rule, [0.001] * 20 + [0.04] * 30))

    def test_the_echo_estimate_follows_louder_playback_but_decays(self):
        rule = BargeInRule(ratio=2.0, min_ms=600, frame_ms=30, floor=0.02)
        self.run_rule(rule, [0.03] * 20 + [0.05] * 5)
        self.assertAlmostEqual(rule.echo, 0.05, places=2)
        self.run_rule(rule, [0.03] * 100)
        self.assertLess(rule.echo, 0.05)


class BargeBase(unittest.TestCase):
    def make(self, enabled=True, mode="vad"):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        cfg = Config(vam_root=self.tmp.name, mic={"mode": mode})
        cfg.audio_dir.mkdir(parents=True, exist_ok=True)
        self.transport = FakeTransport()
        from aibody_companion.pipeline.engines import EngineSet
        engines = EngineSet({"barge_in": {"enabled": enabled, "min_ms": 300}}, env={})
        app = Companion(cfg, self.transport, HeardStt(), EchoLlm(), ToneTts(), gate=EchoGate(clock=self.clock),
                        clock=self.clock, engines=engines)
        return app

    def speak(self, app):
        app.gate.on_speak_sent("u1", 10.0)
        app.gate.on_event({"type": "speech_started", "utterance_id": "u1", "duration": 10})


class BargeInCompanionTests(BargeBase):
    def test_on_by_default_and_can_be_switched_off(self):
        # 22.11.2026 (Don): voice barge-in is on by default (menu toggle "Voice barge-in (headphones)")
        self.assertTrue(settings_file.defaults()["ai"]["barge_in"]["enabled"])
        app = self.make(enabled=False)
        self.assertIsNone(app.input.barge)

    def test_the_user_talks_over_the_body(self):
        app = self.make()
        self.assertIsNotNone(app.input.barge)
        self.speak(app)
        for _ in range(30):
            app.handle_audio_frame(tone(0.03))
        self.assertNotIn("stop_speaking", self.transport.types())
        loud = [tone(wobbly(0.15, i)) for i in range(40)]
        for frame in loud[:15]:
            app.handle_audio_frame(frame)
        self.assertIn("stop_speaking", [c["type"] for c in self.transport.sent])
        self.assertTrue(app.gate.is_open, "the app listens again right away")
        for frame in loud[15:] + [tone(0.003)] * 40:
            app.handle_audio_frame(frame)
        self.assertEqual([m["content"] for m in app.history if m["role"] == "user"], ["hello"], "the utterance went through")

    def test_only_in_voice_activation_mode(self):
        app = self.make(mode="ptt")
        self.speak(app)
        for _ in range(30):
            app.handle_audio_frame(tone(0.03))
        for _ in range(40):
            app.handle_audio_frame(tone(0.3))
        self.assertNotIn("stop_speaking", self.transport.types())

    def test_the_gate_opens_and_the_body_is_told_to_stop(self):
        app = self.make()
        self.speak(app)
        app.gate.on_event({"type": "speech_started", "utterance_id": "u1", "duration": 5})
        self.assertFalse(app.gate.is_open)
        app.voice_barge_in([tone(0.2)] * 3)
        self.assertTrue(app.gate.is_open)
        self.assertIn("stop_speaking", self.transport.types())


class BargeInRealtimeTests(BargeBase):
    def test_realtime_stops_the_answer_and_sends_the_first_words(self):
        from unittest import mock
        from aibody_companion.realtime_voice import RealtimeVoice
        app = self.make()
        app.realtime = RealtimeVoice(app, "dummy-key", connector=lambda *a, **k: None)
        app.realtime.client.ready = True
        app.realtime.client.send = mock.Mock(return_value=True)
        app.realtime.client.append_audio = mock.Mock()
        app.realtime.response_id = "r1"  # an answer is being delivered
        self.speak(app)
        for _ in range(30):
            app.handle_audio_frame(tone(0.03))
        sent_before = app.realtime.client.append_audio.call_count
        for i in range(15):
            app.handle_audio_frame(tone(wobbly(0.15, i)))
        self.assertIn("stop_speaking", [c["type"] for c in self.transport.sent])
        app.realtime.client.send.assert_any_call({"type": "response.cancel"})
        self.assertIsNone(app.realtime.response_id)
        self.assertGreater(app.realtime.client.append_audio.call_count - sent_before, 8, "the user's first words reach the server")
        self.assertTrue(app.gate.is_open)


if __name__ == "__main__":
    unittest.main()
