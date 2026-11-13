import math
import struct
import unittest

from aibody_companion.audio import EnergyVad, SegmenterConfig, UtteranceSegmenter, frame_rms

RATE = 16000
FRAME = 480  # 30 ms


def tone(amplitude: float) -> bytes:
    return b"".join(struct.pack("<h", int(amplitude * 32767 * math.sin(2 * math.pi * 220 * i / RATE)))
                    for i in range(FRAME))


SILENCE = bytes(FRAME * 2)
LOUD = tone(0.3)


class VadTests(unittest.TestCase):
    def test_rms(self):
        self.assertEqual(frame_rms(SILENCE), 0.0)
        self.assertGreater(frame_rms(LOUD), 0.1)

    def test_segment_one_utterance(self):
        seg = UtteranceSegmenter(EnergyVad(), SegmenterConfig(end_silence_ms=300, min_utterance_ms=200))
        out = []
        for frame in [SILENCE] * 10 + [LOUD] * 20 + [SILENCE] * 15:
            r = seg.push(frame)
            if r:
                out.append(r)
        self.assertEqual(len(out), 1)
        # 20 loud frames plus up to 10 frames pre-roll, trailing silence trimmed
        frames = len(out[0]) // (FRAME * 2)
        self.assertGreaterEqual(frames, 20)
        self.assertLessEqual(frames, 30)

    def test_short_blip_ignored(self):
        seg = UtteranceSegmenter(EnergyVad(), SegmenterConfig(end_silence_ms=300, min_utterance_ms=600))
        results = [seg.push(f) for f in [LOUD] * 5 + [SILENCE] * 20]
        self.assertTrue(all(r is None for r in results))

    def test_max_length_cut(self):
        seg = UtteranceSegmenter(EnergyVad(), SegmenterConfig(max_utterance_ms=600))
        results = [seg.push(LOUD) for _ in range(40)]
        self.assertTrue(any(r is not None for r in results))


if __name__ == "__main__":
    unittest.main()
