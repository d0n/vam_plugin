"""Turns microphone frames into utterances according to the current MicSettings.

Voice activation: frames go through gain -> VAD -> UtteranceSegmenter while the echo gate
is open. Push-to-talk: frames are recorded while the button is held (the echo gate is
bypassed when ptt_interrupts is on, because the companion stops the body's speech then);
releasing the button ends the utterance.

Also keeps level statistics for the plugin's level meter.
"""
from __future__ import annotations

from .echo_gate import EchoGate
from .mic_settings import MicSettings
from .vad import EnergyVad, SegmenterConfig, UtteranceSegmenter, apply_gain, frame_rms


class InputProcessor:
    def __init__(self, settings: MicSettings, gate: EchoGate, sample_rate: int = 16000, frame_ms: int = 30):
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.gate = gate
        self.vad = EnergyVad(min_rms=settings.vad_threshold)
        self.segmenter = UtteranceSegmenter(self.vad, self._segmenter_config(settings))
        self.settings = settings
        self.ptt_active = False
        self._ptt_frames: list[bytes] = []
        self._level_peak = 0.0
        self._level_speech = False
        self.apply(settings)

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
        self.settings = settings
        self.vad.min_rms = settings.vad_threshold
        self.segmenter.cfg = self._segmenter_config(settings)
        self.gate.tail_s = settings.echo_tail_s
        if mode_changed:
            self.segmenter.reset()
            self._ptt_frames.clear()
            self.ptt_active = False

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

    def process(self, frame: bytes) -> bytes | None:
        """Feeds one raw mic frame. Returns a finished utterance or None."""
        frame = apply_gain(frame, self.settings.gain)
        rms = frame_rms(frame)
        self._level_peak = max(self._level_peak, rms)
        speech = self.vad.is_speech_rms(rms)
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
            return None
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
