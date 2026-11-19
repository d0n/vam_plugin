"""Voice activity detection and utterance segmentation.

Pure Python so it runs and tests without numpy. Audio is mono 16-bit PCM in frames of
fixed length (default 30 ms at 16 kHz = 480 samples).

EnergyVad is the built-in detector (adaptive noise floor, hysteresis, hangover); WebRtcVad uses the optional
webrtcvad package. make_vad() picks one from the settings mic.vad_engine / mic.vad_strictness.

UtteranceSegmenter turns per-frame speech decisions into utterances:
  - speech starts after `start_ms` of consecutive speech frames
  - it keeps `pre_roll_ms` of audio from before the start so first syllables are kept
  - speech ends after `end_silence_ms` of silence (hangover / timeout)
  - utterances are cut at `max_utterance_ms`, and dropped if shorter than `min_utterance_ms`
"""
from __future__ import annotations

import array
import importlib
import logging
import math
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


def apply_gain(frame: bytes, gain: float) -> bytes:
    """Scales 16-bit PCM samples by gain with clipping. Returns the frame unchanged for gain 1."""
    if abs(gain - 1.0) < 1e-6:
        return frame
    samples = array.array("h")
    samples.frombytes(frame[: len(frame) - (len(frame) % 2)])
    for i, s in enumerate(samples):
        v = int(s * gain)
        samples[i] = 32767 if v > 32767 else (-32768 if v < -32768 else v)
    return samples.tobytes()


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


# "VAD strictness" (mic.vad_strictness, 0..3): higher = ignores more background noise (webrtcvad: its aggressiveness
# mode 0..3). For the built-in detector it sets how far above the noise floor a frame must be to START speech;
# 2 (default) is the old fixed ratio of 3.
STRICTNESS_RATIO = (2.0, 2.5, 3.0, 4.0)
VAD_ENGINES = ("auto", "energy", "webrtc")
WEBRTC_RATES = (8000, 16000, 32000, 48000)
WEBRTC_FRAME_MS = (10, 20, 30)
WEBRTC_INSTALL = "python -m pip install webrtcvad-wheels"


class EnergyVad:
    """Built-in voice detector: energy against an adaptive noise floor, with hysteresis and a short hangover.

      * noise floor: follows the background level on non-speech frames, quickly downwards (a door slam or an
        echo does not leave it too high) and slowly upwards (speech cannot drag it up); several seconds
        of an UNCHANGING level above the threshold (a fan, a hum) become the new floor, so a constant loud noise
        cannot keep the detector open forever
      * start: a frame must exceed max(min_rms, noise_floor * ratio); `min_rms` is the plugin's "VAD threshold"
      * stay: once speech has started it takes only max(0.6 * min_rms, noise_floor * stay_ratio) to continue
        (hysteresis: a quiet syllable does not cut a word), and `hangover_frames` quiet frames are still
        reported as speech (bridges the gaps between syllables). The utterance segmenter adds the long
        end-of-utterance silence and the minimum speech time on top.

    hold() is called while the echo gate is closed: nothing is learned from the body's own voice.
    """

    FLOOR_FALL = 0.25          # per frame, noise floor moving down
    STEADY_FRAMES = 200        # ~6 s of 30 ms frames of an unchanging level = noise, not speech
    STEADY_SPREAD = 0.15       # level spread (mean absolute deviation / mean) below this counts as unchanging

    def __init__(self, ratio: float = 3.0, min_rms: float = 0.01, adapt: float = 0.05,
                 stay_ratio: float | None = None, hangover_frames: int = 3):
        self.ratio = ratio
        self.min_rms = min_rms
        self.adapt = adapt  # per frame, noise floor moving up (scaled down: speech must not raise it)
        self.stay_ratio = stay_ratio if stay_ratio is not None else max(1.2, ratio * 0.55)
        self.hangover_frames = hangover_frames
        self.noise_floor = min_rms / ratio
        self.active = False
        self._hang = 0
        self._steady = 0
        self._mean = 0.0     # running mean level while "speech" (to tell steady noise from speech)
        self._spread = 0.0

    @property
    def name(self) -> str:
        return "energy"

    def is_speech(self, frame: bytes) -> bool:
        return self.is_speech_rms(frame_rms(frame))

    def decide(self, frame: bytes, rms: float) -> bool:
        return self.is_speech_rms(rms)

    def hold(self) -> None:
        """The mic is closed (echo gate): learn nothing, forget any running speech."""
        self.active = False
        self._hang = 0
        self._steady = 0

    def is_speech_rms(self, rms: float) -> bool:
        start = max(self.min_rms, self.noise_floor * self.ratio)
        stay = max(self.min_rms * 0.6, self.noise_floor * self.stay_ratio)
        loud = rms > (stay if self.active else start)
        if loud:
            if not self.active:
                self._mean, self._spread, self._steady = rms, 0.0, 0
            self.active = True
            self._hang = self.hangover_frames
            # Speech wobbles from frame to frame; a fan or hum does not. Several seconds of an unchanging
            # level above the threshold are noise: it becomes the new floor instead of keeping the VAD open.
            self._spread += (abs(rms - self._mean) - self._spread) * 0.05
            self._mean += (rms - self._mean) * 0.05
            self._steady = self._steady + 1 if self._spread < self.STEADY_SPREAD * self._mean else 0
            if self._steady > self.STEADY_FRAMES:
                self.noise_floor = self._mean
                self.active = False
                self._hang = 0
                self._steady = 0
                return False
            return True
        self._steady = 0
        if rms < self.noise_floor:
            self.noise_floor += (rms - self.noise_floor) * self.FLOOR_FALL
        else:
            self.noise_floor += (rms - self.noise_floor) * self.adapt * 0.4
        if self.active and self._hang > 0:
            self._hang -= 1
            return True
        self.active = False
        return False


class WebRtcVad:
    """webrtcvad (Google's WebRTC voice activity detector, a small C extension: `python -m pip install
    webrtcvad-wheels` has Windows wheels) with two additions: a frame only counts as speech when it is also
    above `min_rms` (the plugin's "VAD threshold" keeps its meaning), and a short hangover bridges gaps."""

    def __init__(self, module: Any, aggressiveness: int, sample_rate: int, min_rms: float, hangover_frames: int = 3):
        self._vad = module.Vad(int(aggressiveness))
        self.sample_rate = sample_rate
        self.min_rms = min_rms
        self.hangover_frames = hangover_frames
        self._hang = 0
        self._fallback = EnergyVad(min_rms=min_rms)
        self._warned = False

    @property
    def name(self) -> str:
        return "webrtc"

    def is_speech(self, frame: bytes) -> bool:
        return self.decide(frame, frame_rms(frame))

    def is_speech_rms(self, rms: float) -> bool:  # no frame: the energy rule alone
        return self._fallback.is_speech_rms(rms)

    def hold(self) -> None:
        self._hang = 0
        self._fallback.hold()

    def decide(self, frame: bytes, rms: float) -> bool:
        try:
            raw = bool(self._vad.is_speech(frame, self.sample_rate))
        except Exception as e:  # noqa: BLE001 - e.g. a frame of an odd length
            if not self._warned:
                self._warned = True
                logging.getLogger(__name__).warning("webrtcvad refused a frame (%s); this frame uses the energy rule", e)
            return self._fallback.decide(frame, rms)
        if raw and rms >= self.min_rms:
            self._hang = self.hangover_frames
            return True
        if self._hang > 0:
            self._hang -= 1
            return True
        return False


@dataclass(frozen=True)
class VadInfo:
    """What really runs, for the plugin's status line (mic_state.vad / vad_note)."""
    name: str   # "energy" | "webrtc"
    text: str   # "energy (built-in, adaptive noise floor), strictness 2"
    note: str = ""  # why the requested engine is not used (empty if all is as requested)


def make_vad(engine: str, strictness: int, min_rms: float, sample_rate: int = 16000, frame_ms: int = 30,
             importer: Callable[[str], Any] | None = None) -> tuple[Vad, VadInfo]:
    """Builds the voice detector for the setting mic.vad_engine ("auto" | "energy" | "webrtc") and
    mic.vad_strictness. "auto" and "webrtc" use webrtcvad when it is installed and the frame size fits, else the
    built-in detector (a note says so for "webrtc"; "auto" stays quiet because webrtcvad is optional)."""
    strictness = min(max(int(strictness), 0), 3)
    energy = EnergyVad(ratio=STRICTNESS_RATIO[strictness], min_rms=min_rms)
    built_in = VadInfo("energy", f"energy (built-in, adaptive noise floor), strictness {strictness}")
    if engine == "energy":
        return energy, built_in
    note = ""
    module = None
    if sample_rate not in WEBRTC_RATES or frame_ms not in WEBRTC_FRAME_MS:
        note = (f"webrtcvad needs 8/16/32/48 kHz and 10/20/30 ms frames, this app uses {sample_rate} Hz / {frame_ms} ms, "
                "so the built-in detector is used.")
    else:
        try:
            module = (importer or importlib.import_module)("webrtcvad")
        except ImportError:
            note = f"webrtcvad is not installed, so the built-in detector is used. To use it: {WEBRTC_INSTALL}"
        except Exception as e:  # noqa: BLE001 - a broken native library must not stop the app
            note = f"webrtcvad could not be loaded ({type(e).__name__}), so the built-in detector is used."
    if module is not None:
        try:
            return (WebRtcVad(module, strictness, sample_rate, min_rms),
                    VadInfo("webrtc", f"webrtc (webrtcvad), strictness {strictness}"))
        except Exception as e:  # noqa: BLE001
            note = f"webrtcvad failed to start ({type(e).__name__}), so the built-in detector is used."
    if engine == "auto":
        return energy, VadInfo("energy", built_in.text, "")
    return energy, VadInfo("energy", built_in.text, note)


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

    def push(self, frame: bytes, speech: bool | None = None) -> bytes | None:
        """Feeds one frame. `speech` may be precomputed by the caller (else the VAD decides)."""
        if speech is None:
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
