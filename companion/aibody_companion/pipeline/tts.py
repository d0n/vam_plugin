"""Text to speech. Implementations write a WAV file the plugin can load.

TODO: implement a real engine, e.g. Piper (local), Coqui XTTS (local) or a cloud API.
Output: mono or stereo PCM WAV (VaM plays WAV and OGG; MP3 support depends on platform).
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Protocol


class TextToSpeech(Protocol):
    def synthesize(self, text: str, out_path: Path) -> float:
        """Writes a WAV file and returns its duration in seconds."""
        ...


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


class ToneTts:
    """Mock TTS: a soft warbling tone, ~70 ms per character. Lets you test lip sync,
    speech events and echo gating without any TTS engine installed."""

    def __init__(self, sample_rate: int = 22050, seconds_per_char: float = 0.07, max_seconds: float = 8.0):
        self.sample_rate = sample_rate
        self.seconds_per_char = seconds_per_char
        self.max_seconds = max_seconds

    def synthesize(self, text: str, out_path: Path) -> float:
        duration = min(self.max_seconds, max(0.5, len(text) * self.seconds_per_char))
        n = int(duration * self.sample_rate)
        frames = bytearray()
        for i in range(n):
            t = i / self.sample_rate
            # 4 "syllables" per second so the jaw visibly moves with VaM's lip sync
            envelope = 0.5 + 0.5 * math.sin(2 * math.pi * 4 * t)
            sample = 0.25 * envelope * math.sin(2 * math.pi * (180 + 40 * math.sin(2 * math.pi * 3 * t)) * t)
            frames += struct.pack("<h", int(sample * 32767))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(bytes(frames))
        return duration
