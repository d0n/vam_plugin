import unittest

from aibody_companion.audio import EchoGate


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class EchoGateTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.gate = EchoGate(tail_s=0.5, max_extra_s=2.0, clock=self.clock)

    def test_closed_from_speak_until_tail_after_end(self):
        self.assertTrue(self.gate.is_open)
        self.gate.on_speak_sent("u1", 3.0)
        self.assertFalse(self.gate.is_open)
        self.gate.on_event({"type": "speech_started", "utterance_id": "u1"})
        self.clock.t = 3.0
        self.assertFalse(self.gate.is_open)
        self.gate.on_event({"type": "speech_ended", "utterance_id": "u1"})
        self.assertFalse(self.gate.is_open)  # tail
        self.clock.t = 3.6
        self.assertTrue(self.gate.is_open)

    def test_failsafe_when_events_lost(self):
        self.gate.on_speak_sent("u1", 1.0)
        self.clock.t = 2.5
        self.assertFalse(self.gate.is_open)
        self.clock.t = 3.1
        self.assertTrue(self.gate.is_open)

    def test_audio_failed_reopens(self):
        self.gate.on_speak_sent("u1", 5.0)
        self.gate.on_event({"type": "error", "code": "audio_failed", "reply_to": "u1"})
        self.assertTrue(self.gate.is_open)

    def test_ready_resets(self):
        self.gate.on_event({"type": "speech_started", "utterance_id": "x"})
        self.assertFalse(self.gate.is_open)
        self.gate.on_event({"type": "ready"})
        self.assertTrue(self.gate.is_open)


if __name__ == "__main__":
    unittest.main()
