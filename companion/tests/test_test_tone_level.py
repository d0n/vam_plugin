"""Don, 21.11.2026 20:04: the test tone was very quiet in v42. Both test tones (the bundled AIBodyTest.wav of the
package and the companion's "Test tone via companion" WAV) peak at 0.70 of full scale (+6 dB over 0.35), below 0.8."""
from __future__ import annotations

import importlib.util
import io
import struct
import wave
from pathlib import Path
from unittest import TestCase

from aibody_companion.pipeline import tts

ROOT = Path(__file__).resolve().parents[2]


def peak(pcm: bytes) -> float:
    samples = struct.unpack("<%dh" % (len(pcm) // 2), pcm)
    return max(abs(x) for x in samples) / 32767.0


class TestToneLevelTests(TestCase):
    def test_companion_test_tone_peak(self):
        self.assertEqual(tts.TEST_TONE_PEAK, 0.70)
        p = peak(tts.test_tone_pcm())
        self.assertGreater(p, 0.69)
        self.assertLessEqual(p, 0.8, "clear of clipping")

    def test_bundled_test_wav_peak_matches(self):
        spec = importlib.util.spec_from_file_location("build_var_tone", ROOT / "tools" / "build_var.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        self.assertEqual(build.TEST_TONE_PEAK, tts.TEST_TONE_PEAK)
        with wave.open(io.BytesIO(build.test_tone_wav()), "rb") as w:
            p = peak(w.readframes(w.getnframes()))
        self.assertGreater(p, 0.69)
        self.assertLessEqual(p, 0.8)
