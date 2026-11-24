"""Text to speech. Implementations write a WAV file the plugin can load.

Every engine writes 16-bit PCM WAV into the channel's audio folder: VaM's audio loader
(URLAudioClipManager) plays WAV, and WAV gives the exact duration the speak command and the
echo gate need. Cloud engines request raw PCM and wrap it with write_pcm_wav(); an engine that
gets a complete WAV back writes it as it is (write_audio()).
"""
from __future__ import annotations

import array
import io
import logging
import math
import sys
import struct
import time
import wave
from pathlib import Path
from typing import Protocol

from ..atomicfile import atomic_write_bytes

log = logging.getLogger(__name__)


class TextToSpeech(Protocol):
    def synthesize(self, text: str, out_path: Path) -> float:
        """Writes a WAV file and returns its duration in seconds."""
        ...


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


# Peak of the test tone (fraction of full scale). Don, 21.11.2026 20:04: 0.35 was very quiet in v42; 0.70 is
# +6 dB, still clear of clipping (<= 0.8). Only the test tone; speech volume is unchanged.
TEST_TONE_PEAK = 0.70


def test_tone_pcm(seconds: float = 1.5, rate: int = 22050) -> bytes:
    """A two-note chime (16-bit mono PCM) for the plugin's "Test tone via companion" button;
    4 "syllables" per second so VaM's lip sync moves the jaw. Same sound as the bundled test WAV."""
    frames = bytearray()
    for i in range(int(seconds * rate)):
        t = i / rate
        freq = 440.0 if t < seconds / 2 else 660.0
        fade = min(1.0, t / 0.02, (seconds - t) / 0.05)
        envelope = 0.55 + 0.45 * math.sin(2 * math.pi * 4 * t)
        frames += struct.pack("<h", int(TEST_TONE_PEAK * fade * envelope * math.sin(2 * math.pi * freq * t) * 32767))
    return bytes(frames)


# -- output gain (version 44, Don 21.11.2026 21:01) -------------------------------------------------------------
# The plugin's Speech volume goes up to MAX_SPEECH_VOLUME. VaM's head audio stops at 1, so the part above 1 is applied
# here to every WAV this app writes for the character (TTS, realtime voice, test tone): a plain linear gain, no limiter
# or normalizing (Don 21:16: the user decides how loud). Only samples beyond the 16-bit range are cut to it (a WAV
# cannot hold more), so very loud settings may distort. Default 1 = unchanged bytes.
MAX_SPEECH_VOLUME = 10.0   # 22.11.2026 (Don 04:16): 1000 % in the plugin; was 3.0 (version 44)
_OUTPUT = {"gain": 1.0, "table": None}


def output_gain_for(speech_volume: float) -> float:
    """Speech volume 0..10 -> sample gain: 1 up to volume 1 (the head audio does that part), then the volume itself."""
    try:
        v = float(speech_volume)
    except (TypeError, ValueError):
        return 1.0
    if math.isnan(v):
        return 1.0
    return max(1.0, min(MAX_SPEECH_VOLUME, v))


def gained_sample(value: int, gain: float) -> int:
    """One 16-bit sample times the gain, cut only to the 16-bit range (no limiter)."""
    return max(-32768, min(32767, int(round(value * gain))))


def gain_table(gain: float) -> list[int]:
    """All 65536 16-bit sample values (index = value + 32768) after the linear gain."""
    return [gained_sample(i - 32768, gain) for i in range(65536)]


def set_output_gain(speech_volume: float) -> float:
    """Called with the plugin's Speech volume (config event "body", config.json body.speech_volume)."""
    gain = output_gain_for(speech_volume)
    if gain != _OUTPUT["gain"]:
        _OUTPUT["gain"] = gain
        _OUTPUT["table"] = None if gain == 1.0 else gain_table(gain)
    return gain


def output_gain() -> float:
    return _OUTPUT["gain"]


def apply_gain(pcm16: bytes, gain: float | None = None) -> bytes:
    """16-bit little-endian PCM with the output gain (or the given one), linear; gain 1 = unchanged."""
    if gain is None:
        gain, table = _OUTPUT["gain"], _OUTPUT["table"]
    else:
        gain = output_gain_for(gain)
        table = None if gain == 1.0 else gain_table(gain)
    if gain == 1.0 or table is None or not pcm16:
        return pcm16
    samples = array.array("h")
    samples.frombytes(pcm16[: len(pcm16) - len(pcm16) % 2])
    if sys.byteorder != "little":
        samples.byteswap()
    out = array.array("h", [table[v + 32768] for v in samples])
    if sys.byteorder != "little":
        out.byteswap()
    return out.tobytes()


LAST_WRITE_S = {"s": 0.0}  # how long the last WAV write took (latency breakdown "file write")

# After v45 (Don 22.11.2026 04:02, "Speech volume 3 made no noticeable difference"): the first speech WAV, and the first
# after every gain change, is measured and logged (INFO): its peak before the gain and how many samples the gain cuts at
# full scale. A voice that already peaks near 0 dBFS cannot get much louder in the file; the log shows that plainly.
_LEVEL = {"logged_gain": None}


def level_report(pcm16: bytes, gain: float) -> dict:
    """Peak (dBFS, before the gain), peak after the gain and the share of samples cut at full scale by the gain."""
    samples = array.array("h")
    samples.frombytes(pcm16[: len(pcm16) - len(pcm16) % 2])
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return {"peak_dbfs": None, "gained_peak_dbfs": None, "clipped": 0.0}
    peak = max(max(samples), -min(samples), 1)
    clipped = 0.0
    if gain > 1.0:
        limit = 32767.0 / gain
        clipped = sum(1 for v in samples if v > limit or v < -limit - 1) / len(samples)
    return {"peak_dbfs": round(20 * math.log10(peak / 32768.0), 1),
            "gained_peak_dbfs": round(20 * math.log10(min(32768.0, peak * gain) / 32768.0), 1),
            "clipped": clipped}


def log_level_once(pcm16: bytes) -> None:
    gain = _OUTPUT["gain"]
    if _LEVEL["logged_gain"] == gain:
        return
    _LEVEL["logged_gain"] = gain
    r = level_report(pcm16, gain)
    if r["peak_dbfs"] is None:
        return
    log.info("Speech level: peak %.1f dBFS before the gain, gain x%.2f -> peak %.1f dBFS, %.1f%% of the samples cut at "
             "full scale%s", r["peak_dbfs"], gain, r["gained_peak_dbfs"], 100 * r["clipped"],
             " (the file is at its limit: higher Speech volume only adds distortion)" if r["clipped"] > 0.01 else "")


def write_pcm_wav(pcm16: bytes, sample_rate: int, out_path: Path, channels: int = 1) -> float:
    """Wraps raw signed 16-bit little-endian PCM in a WAV file (with the output gain); returns its duration."""
    started = time.perf_counter()
    if len(pcm16) % (2 * channels):
        pcm16 = pcm16[: len(pcm16) - len(pcm16) % (2 * channels)]
    if not pcm16:
        raise ValueError("no audio data")
    log_level_once(pcm16)
    pcm16 = apply_gain(pcm16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm16)
    atomic_write_bytes(out_path, buf.getvalue(), durable=False)  # temp name, replace: complete or absent
    LAST_WRITE_S["s"] = time.perf_counter() - started
    return len(pcm16) / (2 * channels) / float(sample_rate)


def write_audio(data: bytes, sample_rate: int, out_path: Path) -> float:
    """Writes a TTS answer: a complete WAV (starts with RIFF) as is, else raw 16-bit PCM. With an output gain above 1
    a 16-bit WAV is re-written with the gain (other sample formats stay as they are)."""
    if data[:4] == b"RIFF" and _OUTPUT["gain"] != 1.0:
        try:
            with wave.open(io.BytesIO(data), "rb") as w:
                if w.getsampwidth() == 2:
                    return write_pcm_wav(w.readframes(w.getnframes()), w.getframerate(), out_path, w.getnchannels())
        except (wave.Error, EOFError):
            pass
    if data[:4] == b"RIFF":
        started = time.perf_counter()
        atomic_write_bytes(out_path, data, durable=False)
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
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(bytes(frames))
        atomic_write_bytes(out_path, buf.getvalue(), durable=False)  # was written in place: a reader could see half a file
        return duration
