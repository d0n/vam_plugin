"""Echo gate: keeps the microphone closed while the body is speaking.

The VaM character plays TTS through the speakers, which the microphone hears again.
Without headphones this would make the AI answer itself. Strategy (same as Voxta):

  * close the gate as soon as the companion sends a `speak` command
    (playback starts after a short load delay, sound must not leak in before)
  * keep it closed while the plugin reports `speech_started` ... `speech_ended`
  * keep it closed for `tail_s` afterwards (room reverb, audio buffers)
  * failsafe: reopen after `expected duration + max_extra_s` if events got lost,
    or right away when the plugin reports an `audio_failed` error

TODO: barge-in (let the user interrupt). Needs acoustic echo cancellation (e.g. WebRTC
AEC / speexdsp) or a much higher VAD threshold while speaking; then send stop_speaking.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class EchoGate:
    def __init__(
        self,
        tail_s: float = 0.4,
        max_extra_s: float = 5.0,
        max_speaking_s: float = 120.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.tail_s = tail_s
        self.max_extra_s = max_extra_s
        self.max_speaking_s = max_speaking_s
        self._speaking_since = 0.0
        self._clock = clock
        self._pending: dict[str, float] = {}  # utterance id -> failsafe deadline
        self._speaking = False
        self._closed_until = 0.0

    def on_speak_sent(self, utterance_id: str, expected_duration_s: float | None) -> None:
        duration = expected_duration_s if expected_duration_s is not None else 30.0
        self._pending[utterance_id] = self._clock() + duration + self.max_extra_s

    def on_event(self, event: dict[str, Any]) -> None:
        type_ = event.get("type")
        uid = event.get("utterance_id") or event.get("reply_to") or ""
        if type_ == "speech_started":
            self._speaking = True
            self._speaking_since = self._clock()
            # Playback started: replace the load failsafe with one based on actual start.
            if uid in self._pending:
                self._pending[uid] = max(self._pending[uid], self._clock() + self.max_extra_s)
        elif type_ == "speech_ended":
            self._speaking = False
            self._pending.pop(uid, None)
            self._closed_until = self._clock() + self.tail_s
        elif type_ == "error" and event.get("code") == "audio_failed":
            self._pending.pop(uid, None)
        elif type_ in ("ready", "shutdown"):
            # Plugin (re)started: nothing can be playing.
            self._speaking = False
            self._pending.clear()

    @property
    def is_open(self) -> bool:
        now = self._clock()
        for uid, deadline in list(self._pending.items()):
            if now > deadline:
                del self._pending[uid]  # failsafe: lost events
        if self._speaking and now - self._speaking_since > self.max_speaking_s:
            self._speaking = False  # failsafe: speech_ended got lost
        return not self._speaking and not self._pending and now >= self._closed_until

    def force_open(self) -> None:
        self._speaking = False
        self._pending.clear()
        self._closed_until = 0.0
