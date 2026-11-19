"""Turns microphone frames into utterances according to the current MicSettings.

Voice activation: frames go through gain -> VAD -> UtteranceSegmenter while the echo gate
is open. While it is closed (the body is talking, plus the tail) the VAD sees nothing at all: it learns no
noise floor from the body's own voice and a running utterance is dropped. Push-to-talk: frames are recorded
while the button is held (the echo gate is bypassed when ptt_interrupts is on, because the companion stops the body's speech then);
releasing the button ends the utterance.

Also keeps level statistics for the plugin's level meter.
"""
from __future__ import annotations

import logging

from .barge import BargeInRule
from .echo_gate import EchoGate
from .mic_settings import MicSettings
from .vad import SegmenterConfig, UtteranceSegmenter, apply_gain, frame_rms, make_vad

log = logging.getLogger(__name__)


class InputProcessor:
    def __init__(self, settings: MicSettings, gate: EchoGate, sample_rate: int = 16000, frame_ms: int = 30,
                 silero_model: str | None = None):
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.gate = gate
        self.silero_model = silero_model  # path of silero_vad.onnx (the file may not exist)
        self.barge: BargeInRule | None = None  # voice barge-in by a loudness rule (ai.barge_in), off by default
        self.barge_frames: list[bytes] | None = None  # the user's stretch when the rule fired, until taken
        self.vad, self.vad_info = make_vad(settings.vad_engine, settings.vad_strictness, settings.vad_threshold,
                                           sample_rate, frame_ms, silero_model=silero_model)
        self.segmenter = UtteranceSegmenter(self.vad, self._segmenter_config(settings))
        self.settings = settings
        self._log_vad()
        self.ptt_active = False
        self._ptt_frames: list[bytes] = []
        self._level_peak = 0.0
        self._level_speech = False
        self.apply(settings)

    def _log_vad(self) -> None:
        log.info("Voice detection: %s%s", self.vad_info.text, f" - {self.vad_info.note}" if self.vad_info.note else "")

    def _segmenter_config(self, s: MicSettings) -> SegmenterConfig:
        return SegmenterConfig(
            sample_rate=self.sample_rate,
            frame_ms=self.frame_ms,
            end_silence_ms=s.end_silence_ms,
            min_utterance_ms=s.min_utterance_ms,
            max_utterance_ms=s.max_utterance_ms,
        )

    def apply(self, settings: MicSettings) -> None:
        mode_changed = settings.mode != self.settings.mode
        detector_changed = (settings.vad_engine, settings.vad_strictness) != (
            self.settings.vad_engine, self.settings.vad_strictness)
        self.settings = settings
        if detector_changed:
            self.vad, self.vad_info = make_vad(settings.vad_engine, settings.vad_strictness, settings.vad_threshold,
                                               self.sample_rate, self.frame_ms, silero_model=self.silero_model)
            self.segmenter.vad = self.vad
            self.segmenter.reset()
            self._log_vad()
        self.vad.min_rms = settings.vad_threshold
        self.segmenter.cfg = self._segmenter_config(settings)
        self.gate.tail_s = settings.echo_tail_s
        if mode_changed:
            self.segmenter.reset()
            self._ptt_frames.clear()
            self.ptt_active = False

    # -- voice barge-in by a loudness rule -----------------------------------------------

    def watch_barge(self, frame: bytes, rms: float) -> list[bytes] | None:
        """Gate closed (the body talks): True-ish result = the user talks over it. Frames of that stretch."""
        if self.barge is None or self.settings.mode != "vad" or not self.settings.enabled:
            return None
        return self.barge.push(frame, rms, self.gate.is_speaking)

    def take_barge(self) -> list[bytes] | None:
        frames, self.barge_frames = self.barge_frames, None
        return frames

    # -- push-to-talk ----------------------------------------------------------------

    def set_ptt(self, active: bool) -> bytes | None:
        """Press/release. Returns the recorded utterance on release (if long enough)."""
        if self.settings.mode != "ptt":
            self.ptt_active = False
            return None
        was = self.ptt_active
        self.ptt_active = active
        if active and not was:
            self._ptt_frames = []
            return None
        if was and not active:
            return self._finish_ptt()
        return None

    def _finish_ptt(self) -> bytes | None:
        frames, self._ptt_frames = self._ptt_frames, []
        if len(frames) * self.frame_ms < self.settings.min_utterance_ms:
            return None
        return b"".join(frames)

    # -- frames ----------------------------------------------------------------------

    def meter(self, frame: bytes) -> bytes:
        """Gain + level statistics only (realtime mode: the server does turn detection).
        Returns the frame with gain applied."""
        frame = apply_gain(frame, self.settings.gain)
        rms = frame_rms(frame)
        self._level_peak = max(self._level_peak, rms)
        self._level_speech = self._level_speech or self._detect(frame, rms)
        return frame

    def _detect(self, frame: bytes, rms: float) -> bool:
        """Speech decision of the VAD; only while the echo gate is open (else the VAD is on hold)."""
        if not self.gate.is_open:
            self.vad.hold()
            return False
        return self.vad.decide(frame, rms)

    def process(self, frame: bytes, gained: bool = False) -> bytes | None:
        """Feeds one raw mic frame (gained=True: gain was applied already, e.g. frames kept by the barge-in rule).
        Returns a finished utterance or None."""
        if not gained:
            frame = apply_gain(frame, self.settings.gain)
        rms = frame_rms(frame)
        self._level_peak = max(self._level_peak, rms)
        speech = self._detect(frame, rms)
        self._level_speech = self._level_speech or speech

        if self.settings.mode == "ptt":
            if not self.ptt_active:
                return None
            if not self.settings.ptt_interrupts and not self.gate.is_open:
                return None
            self._ptt_frames.append(frame)
            if len(self._ptt_frames) * self.frame_ms >= self.settings.max_utterance_ms:
                return self._finish_ptt()
            return None

        if not self.gate.is_open:
            # The body is talking: what the mic hears now is (mostly) our own voice.
            if self.segmenter.in_speech:
                self.segmenter.reset()
            frames = self.watch_barge(frame, rms)
            if frames:
                self.barge_frames = frames  # the companion stops the body and feeds them back (take_barge)
            return None
        if self.barge is not None:
            self.barge.reset()  # the gate is open: the next answer teaches the echo level anew
        return self.segmenter.push(frame, speech)

    def take_level(self) -> dict:
        """Level since the last call, for the plugin's meter."""
        level = {
            "rms": round(self._level_peak, 5),
            "speech": self._level_speech or self.segmenter.in_speech or self.ptt_active,
            "gate_open": self.gate.is_open,
        }
        self._level_peak = 0.0
        self._level_speech = False
        return level
