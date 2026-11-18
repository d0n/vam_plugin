"""The plugin's sliders cover exactly the ranges config.json / the companion accept, so a value from
the file is never clamped by a slider and written back changed."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from aibody_companion.audio.mic_settings import LIMITS
from aibody_companion.settings_file import RANGES

SRC = Path(__file__).resolve().parents[2] / "src" / "AIBody"

# slider label in the plugin -> range on the companion side
SLIDERS = {
    "VAD threshold": LIMITS["vad_threshold"],
    "Silence timeout (ms)": LIMITS["end_silence_ms"],
    "Min utterance (ms)": LIMITS["min_utterance_ms"],
    "Max utterance (ms)": LIMITS["max_utterance_ms"],
    "Echo gate tail (s)": LIMITS["echo_tail_s"],
    "Input gain": LIMITS["gain"],
    "Speech volume": RANGES[("body", "speech_volume")],
    "Idle intensity": RANGES[("body", "idle_intensity")],
    "Breaths per minute": RANGES[("body", "breaths_per_minute")],
    "Breath depth": RANGES[("body", "breath_depth")],
    # storable name (stored in scenes); shown as "Companion inbox poll interval (s)" since version 19
    "File poll interval (s)": RANGES[("advanced", "file_poll_interval_s")],
    "Proactive idle (s)": RANGES[("ai", "proactive", "idle_seconds")],
}

FLOAT = re.compile(r'new JSONStorableFloat\("([^"]+)",\s*[-\d.]+f,.*?,\s*([-\d.]+)f,\s*([-\d.]+)f\)')


def plugin_sliders() -> dict[str, tuple[float, float]]:
    found = {}
    for path in SRC.glob("*.cs"):
        for m in FLOAT.finditer(path.read_text(encoding="utf-8")):
            found[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return found


class SliderRangeTests(unittest.TestCase):
    def test_every_config_slider_matches_the_companion_range(self):
        found = plugin_sliders()
        for label, (lo, hi) in SLIDERS.items():
            with self.subTest(label=label):
                self.assertIn(label, found)
                self.assertEqual(found[label], (float(lo), float(hi)))


if __name__ == "__main__":
    unittest.main()
