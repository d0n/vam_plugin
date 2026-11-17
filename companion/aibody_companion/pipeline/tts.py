"""Text to speech. Implementations write a WAV file the plugin can load.

Every engine writes 16-bit PCM WAV into the channel's audio folder: VaM's audio loader
(URLAudioClipManager) plays WAV, and WAV gives the exact duration the speak command and the
echo gate need. Cloud engines request raw PCM and wrap it with write_pcm_wav(); an engine that
gets a complete WAV back writes it as it is (write_audio()).
"""
from __future__ import annotations

import io
import math
import struct
import time
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


def test_tone_pcm(seconds: float = 1.5, rate: int = 22050) -> bytes:
    """A two-note chime (16-bit mono PCM) for the plugin's "Test-Ton über Companion" button;
    4 "syllables" per second so VaM's lip sync moves the jaw. Same sound as the bundled test WAV."""
    frames = bytearray()
    for i in range(int(seconds * rate)):
        t = i / rate
        freq = 440.0 if t < seconds / 2 else 660.0
        fade = min(1.0, t / 0.02, (seconds - t) / 0.05)
        envelope = 0.55 + 0.45 * math.sin(2 * math.pi * 4 * t)
        frames += struct.pack("<h", int(0.35 * fade * envelope * math.sin(2 * math.pi * freq * t) * 32767))
    return bytes(frames)


LAST_WRITE_S = {"s": 0.0}  # how long the last WAV write took (latency breakdown "Datei")


def write_pcm_wav(pcm16: bytes, sample_rate: int, out_path: Path, channels: int = 1) -> float:
    """Wraps raw signed 16-bit little-endian PCM in a WAV file; returns its duration."""
    started = time.perf_counter()
    if len(pcm16) % (2 * channels):
        pcm16 = pcm16[: len(pcm16) - len(pcm16) % (2 * channels)]
    if not pcm16:
        raise ValueError("no audio data")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".part")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm16)
    tmp.replace(out_path)
    LAST_WRITE_S["s"] = time.perf_counter() - started
    return len(pcm16) / (2 * channels) / float(sample_rate)


def write_audio(data: bytes, sample_rate: int, out_path: Path) -> float:
    """Writes a TTS answer: a complete WAV (starts with RIFF) as is, else raw 16-bit PCM."""
    if data[:4] == b"RIFF":
        started = time.perf_counter()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(out_path)
        LAST_WRITE_S["s"] = time.perf_counter() - started
        return wav_duration(out_path)
    return write_pcm_wav(data, sample_rate, out_path)


def pcm_to_wav_bytes(pcm16: bytes, sample_rate: int) -> bytes:
    """Mono 16-bit PCM -> WAV file bytes (for uploading microphone audio)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm16)
    return buf.getvalue()


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
