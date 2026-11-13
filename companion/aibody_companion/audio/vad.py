"""Voice activity detection and utterance segmentation.

Pure Python so it runs and tests without numpy. Audio is mono 16-bit PCM in frames of
fixed length (default 30 ms at 16 kHz = 480 samples).

EnergyVad is a simple adaptive energy detector. It is good enough to get the pipeline
running; swap in webrtcvad or Silero VAD (TODO) by implementing `is_speech(frame)`.

UtteranceSegmenter turns per-frame speech decisions into utterances:
  - speech starts after `start_ms` of consecutive speech frames
  - it keeps `pre_roll_ms` of audio from before the start so first syllables are kept
  - speech ends after `end_silence_ms` of silence (hangover / timeout)
  - utterances are cut at `max_utterance_ms`, and dropped if shorter than `min_utterance_ms`
"""
from __future__ import annotations

import array
import math
from collections import deque
from dataclasses import dataclass
from typing import Protocol


def frame_rms(frame: bytes) -> float:
    """RMS of a 16-bit little endian PCM frame, normalized to 0..1."""
    samples = array.array("h")
    samples.frombytes(frame[: len(frame) - (len(frame) % 2)])
    if not samples:
        return 0.0
    acc = sum(s * s for s in samples)
    return math.sqrt(acc / len(samples)) / 32768.0


class Vad(Protocol):
    def is_speech(self, frame: bytes) -> bool: ...


class EnergyVad:
    """Adaptive energy threshold: speech if rms > noise_floor * ratio and above min_rms."""

    def __init__(self, ratio: float = 3.0, min_rms: float = 0.01, adapt: float = 0.05):
        self.ratio = ratio
        self.min_rms = min_rms
        self.adapt = adapt
        self.noise_floor = min_rms / ratio

    def is_speech(self, frame: bytes) -> bool:
        rms = frame_rms(frame)
        speech = rms > max(self.min_rms, self.noise_floor * self.ratio)
        if not speech:
            # Track the background level only on non-speech frames.
            self.noise_floor += (rms - self.noise_floor) * self.adapt
        return speech


@dataclass
class SegmenterConfig:
    sample_rate: int = 16000
    frame_ms: int = 30
    start_ms: int = 90
    end_silence_ms: int = 700
    pre_roll_ms: int = 300
    min_utterance_ms: int = 300
    max_utterance_ms: int = 20000


class UtteranceSegmenter:
    """Feed frames with push(); returns a finished utterance (bytes) or None."""

    def __init__(self, vad: Vad, config: SegmenterConfig | None = None):
        self.vad = vad
        self.cfg = config or SegmenterConfig()
        self._pre_roll: deque[bytes] = deque(maxlen=max(1, self.cfg.pre_roll_ms // self.cfg.frame_ms))
        self._frames: list[bytes] = []
        self._speech_run = 0
        self._silence_run = 0
        self.in_speech = False

    @property
    def frame_bytes(self) -> int:
        return self.cfg.sample_rate * self.cfg.frame_ms // 1000 * 2

    def reset(self) -> None:
        """Drops any partial utterance (used when the echo gate closes)."""
        self._pre_roll.clear()
        self._frames.clear()
        self._speech_run = 0
        self._silence_run = 0
        self.in_speech = False

    def push(self, frame: bytes) -> bytes | None:
        speech = self.vad.is_speech(frame)
        ms = self.cfg.frame_ms

        if not self.in_speech:
            self._pre_roll.append(frame)
            self._speech_run = self._speech_run + 1 if speech else 0
            if self._speech_run * ms >= self.cfg.start_ms:
                self.in_speech = True
                self._silence_run = 0
                self._frames = list(self._pre_roll)
                self._pre_roll.clear()
            return None

        self._frames.append(frame)
        self._silence_run = 0 if speech else self._silence_run + 1
        duration_ms = len(self._frames) * ms

        if self._silence_run * ms >= self.cfg.end_silence_ms or duration_ms >= self.cfg.max_utterance_ms:
            frames = list(self._frames)  # copy: reset() clears the list in place
            if self._silence_run:
                frames = frames[: len(frames) - self._silence_run] or frames
            self.reset()
            if len(frames) * ms < self.cfg.min_utterance_ms:
                return None
            return b"".join(frames)
        return None
