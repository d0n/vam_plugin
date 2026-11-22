"""Voice barge-in without headphones, by a loudness rule (version 29).

While the body speaks the microphone is closed on purpose (it would hear the speakers). A real echo canceller
is not possible here (the reference signal lives in VaM), so this is a RULE instead: during the body's
speech the mic level of the echo is learned as a decaying peak; a stretch of frames clearly LOUDER than that
echo (`ratio` times, and above `floor`) that lasts `min_ms` is the user talking over the character. Then the
caller stops the body, opens the gate and gets the frames of that stretch back (so the first words are kept).

On by default since 22.11.2026 (ai.barge_in.enabled = the menu toggle "Voice barge-in (headphones)"). It needs the user to be clearly louder at the microphone than the speakers
are: a quiet voice or loud speakers will not trigger it, a very loud TTS peak or a door slam may.
"""
from __future__ import annotations

from collections import deque


class BargeInRule:
    RISE = 1.1  # 22.11.2026: max. rise of the echo estimate per frame after the warm-up (+10 % per 30 ms)

    def __init__(self, ratio: float = 2.0, min_ms: int = 600, frame_ms: int = 30, floor: float = 0.02,
                 warmup_ms: int = 450, decay: float = 0.995):
        self.ratio = ratio
        self.min_frames = max(1, min_ms // frame_ms)
        self.warmup_frames = max(1, warmup_ms // frame_ms)
        self.floor = floor
        self.decay = decay
        self._recent: deque[bytes] = deque(maxlen=self.min_frames + 8)
        self.reset()

    def reset(self) -> None:
        """The gate is open again (or a new answer starts): learn the echo anew."""
        self.echo = 0.0          # decaying peak of the echo level
        self._warm = 0           # speaking frames seen (the first ones only teach)
        self._loud = 0           # leaky count of loud frames
        self._recent.clear()

    def push(self, frame: bytes, rms: float, speaking: bool) -> list[bytes] | None:
        """One frame while the gate is closed. `speaking` = the body really plays audio now (speech_started
        seen). Returns the frames of the user's stretch when the rule fires, else None."""
        if not speaking:
            return None  # waiting for playback / between clips / the tail: nothing to compare with
        self._recent.append(frame)
        loud = self._warm >= self.warmup_frames and rms >= self.floor and rms > self.echo * self.ratio
        self._warm += 1
        if loud:
            self._loud += 1
            if self._loud >= self.min_frames:
                frames = list(self._recent)
                self.reset()
                return frames
            return None
        self._loud = max(0, self._loud - 1)
        if self._loud == 0:
            # echo teaches only with frames that are not loud, and not while a loud stretch is building (22.11.2026: the
            # quieter syllables of the user talking over the body raised the echo and the rule never fired)
            if self._warm <= self.warmup_frames or self.echo <= 0.0:
                self.echo = max(rms, self.echo * self.decay)   # warm-up: learn her level fast
            else:
                # after the warm-up the estimate rises at most RISE per frame: her own voice gets louder smoothly and is
                # followed within a few frames, the first (quieter) syllable of the user does not raise it at once
                self.echo = max(self.echo * self.decay, min(rms, self.echo * self.RISE))
        return None
