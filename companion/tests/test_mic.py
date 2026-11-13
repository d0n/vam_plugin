import math
import struct
import unittest

from aibody_companion.audio import (
    EchoGate,
    InputProcessor,
    MicController,
    MicSettings,
    apply_gain,
    apply_mic_config,
    frame_rms,
)

RATE = 16000
FRAME = 480


def tone(amplitude: float) -> bytes:
    return b"".join(struct.pack("<h", int(amplitude * 32767 * math.sin(2 * math.pi * 220 * i / RATE)))
                    for i in range(FRAME))


SILENCE = bytes(FRAME * 2)
LOUD = tone(0.3)
QUIET = tone(0.005)


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class MicSettingsTests(unittest.TestCase):
    def test_defaults_roundtrip(self):
        s, errors = apply_mic_config(MicSettings(), MicSettings().to_dict())
        self.assertEqual(errors, [])
        self.assertEqual(s, MicSettings())

    def test_clamps_numbers(self):
        s, errors = apply_mic_config(MicSettings(), {"gain": 100, "end_silence_ms": 10, "vad_threshold": 0})
        self.assertEqual(errors, [])
        self.assertEqual(s.gain, 8.0)
        self.assertEqual(s.end_silence_ms, 200)
        self.assertIsInstance(s.end_silence_ms, int)
        self.assertEqual(s.vad_threshold, 0.001)

    def test_rejects_bad_values_and_keeps_old(self):
        s, errors = apply_mic_config(MicSettings(), {"mode": "always", "enabled": "yes", "gain": "loud", "bogus": 1})
        self.assertEqual(len(errors), 4)
        self.assertEqual(s, MicSettings())

    def test_min_must_be_below_max(self):
        s, errors = apply_mic_config(MicSettings(), {"min_utterance_ms": 5000, "max_utterance_ms": 1000})
        self.assertEqual(len(errors), 1)
        self.assertEqual((s.min_utterance_ms, s.max_utterance_ms), (300, 20000))

    def test_not_a_dict(self):
        self.assertEqual(len(apply_mic_config(MicSettings(), None)[1]), 1)


class GainTests(unittest.TestCase):
    def test_gain_scales_and_clips(self):
        self.assertAlmostEqual(frame_rms(apply_gain(QUIET, 2.0)), 2 * frame_rms(QUIET), places=3)
        self.assertLessEqual(frame_rms(apply_gain(LOUD, 8.0)), 1.0)
        self.assertIs(apply_gain(LOUD, 1.0), LOUD)


class InputProcessorTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.gate = EchoGate(clock=self.clock)

    def test_vad_mode_respects_threshold_and_gain(self):
        p = InputProcessor(MicSettings(vad_threshold=0.05, end_silence_ms=300), self.gate)
        out = [p.process(f) for f in [QUIET] * 30 + [SILENCE] * 20]
        self.assertTrue(all(o is None for o in out), "quiet speech is below the threshold")
        p.apply(MicSettings(vad_threshold=0.05, end_silence_ms=300, gain=8.0))
        p.process(SILENCE)
        out = [p.process(f) for f in [tone(0.05)] * 30 + [SILENCE] * 20]
        self.assertTrue(any(o for o in out), "gain lifts it above the threshold")

    def test_vad_mode_gated_while_speaking(self):
        p = InputProcessor(MicSettings(end_silence_ms=300), self.gate)
        self.gate.on_speak_sent("u1", 5.0)
        out = [p.process(f) for f in [LOUD] * 30 + [SILENCE] * 20]
        self.assertTrue(all(o is None for o in out))

    def test_ptt_records_between_press_and_release(self):
        p = InputProcessor(MicSettings(mode="ptt", min_utterance_ms=200), self.gate)
        self.assertIsNone(p.process(LOUD))  # not pressed: ignored
        self.assertIsNone(p.set_ptt(True))
        for _ in range(20):
            self.assertIsNone(p.process(SILENCE))  # silence does not end a PTT utterance
        utterance = p.set_ptt(False)
        self.assertEqual(len(utterance), 20 * FRAME * 2)

    def test_ptt_too_short_is_dropped(self):
        p = InputProcessor(MicSettings(mode="ptt", min_utterance_ms=600), self.gate)
        p.set_ptt(True)
        for _ in range(5):
            p.process(LOUD)
        self.assertIsNone(p.set_ptt(False))

    def test_ptt_bypasses_gate_only_with_interrupts(self):
        self.gate.on_speak_sent("u1", 5.0)
        p = InputProcessor(MicSettings(mode="ptt", min_utterance_ms=100, ptt_interrupts=False), self.gate)
        p.set_ptt(True)
        for _ in range(10):
            p.process(LOUD)
        self.assertIsNone(p.set_ptt(False))
        p.apply(MicSettings(mode="ptt", min_utterance_ms=100, ptt_interrupts=True))
        p.set_ptt(True)
        for _ in range(10):
            p.process(LOUD)
        self.assertIsNotNone(p.set_ptt(False))

    def test_ptt_ignored_in_vad_mode(self):
        p = InputProcessor(MicSettings(mode="vad"), self.gate)
        p.set_ptt(True)
        self.assertFalse(p.ptt_active)

    def test_level(self):
        p = InputProcessor(MicSettings(), self.gate)
        p.process(LOUD)
        p.process(SILENCE)
        level = p.take_level()
        self.assertGreater(level["rms"], 0.1)
        self.assertTrue(level["speech"])
        self.assertTrue(level["gate_open"])
        self.assertEqual(p.take_level()["rms"], 0.0)


class FakeCapture:
    instances = []

    def __init__(self, rate, ms, device):
        self.device = device
        self.started = False
        self.stopped = False
        FakeCapture.instances.append(self)

    def start(self):
        if self.device == "broken":
            raise RuntimeError("device not found")
        self.started = True

    def stop(self):
        self.stopped = True

    def frames(self):
        return iter([SILENCE])


class MicControllerTests(unittest.TestCase):
    def setUp(self):
        FakeCapture.instances = []
        self.mic = MicController(capture_factory=FakeCapture)

    def test_follows_enabled_and_device(self):
        self.mic.apply(MicSettings(enabled=True))
        self.assertTrue(self.mic.capturing)
        self.mic.apply(MicSettings(enabled=True))  # unchanged: no restart
        self.assertEqual(len(FakeCapture.instances), 1)
        self.mic.apply(MicSettings(enabled=True, device="USB"))
        self.assertEqual(len(FakeCapture.instances), 2)
        self.assertTrue(FakeCapture.instances[0].stopped)
        self.assertEqual(FakeCapture.instances[1].device, "USB")
        self.mic.apply(MicSettings(enabled=False))
        self.assertFalse(self.mic.capturing)

    def test_error_is_reported(self):
        self.mic.apply(MicSettings(enabled=True, device="broken"))
        self.assertFalse(self.mic.capturing)
        self.assertIn("device not found", self.mic.error)
        self.mic.apply(MicSettings(enabled=True))
        self.assertTrue(self.mic.capturing)
        self.assertIsNone(self.mic.error)


if __name__ == "__main__":
    unittest.main()
