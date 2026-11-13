"""Echo gate: keeps the microphone closed while the body is speaking.

The VaM character plays TTS through the speakers, which the microphone hears again.
Without headphones this would make the AI answer itself. Strategy (same as Voxta):

  * close the gate as soon as the companion sends a `speak` command
    (playback starts after a short load delay, sound must not leak in before)
  * keep it closed while any sent utterance has not reported `speech_ended`
    (utterances play from a queue in the plugin, so several can be pending)
  * keep it closed for `tail_s` after audio really stopped (room reverb, audio buffers)
  * failsafes: every pending utterance gets a deadline (expected queue end + max_extra_s,
    refreshed with the real clip length on `speech_started`), and a speaking state longer
    than max_speaking_s is dropped, in case events get lost
  * `error` with code `audio_failed` or `no_person` (no body to play it), or `speech_ended`
    with reason cancelled/failed, release the utterance without a tail (nothing was played)

TODO: barge-in in voice-activation mode needs acoustic echo cancellation (e.g. WebRTC AEC /
speexdsp). Push-to-talk already allows interrupting (see InputProcessor).
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

NO_TAIL_REASONS = {"cancelled", "failed"}
NO_PLAYBACK_ERRORS = {"audio_failed", "no_person"}


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
        self._clock = clock
        self._pending: dict[str, float] = {}  # utterance id -> failsafe deadline
        self._expected_end = 0.0  # estimated end of the plugin's playback queue
        self._speaking = False
        self._speaking_since = 0.0
        self._closed_until = 0.0

    def on_speak_sent(self, utterance_id: str, expected_duration_s: float | None, interrupt: bool = False) -> None:
        now = self._clock()
        duration = expected_duration_s if expected_duration_s is not None else 30.0
        if interrupt:
            self._pending.clear()
            self._expected_end = now
        self._expected_end = max(now, self._expected_end) + duration
        self._pending[utterance_id] = self._expected_end + self.max_extra_s

    def on_event(self, event: dict[str, Any]) -> None:
        type_ = event.get("type")
        uid = event.get("utterance_id") or event.get("reply_to") or ""
        now = self._clock()
        if type_ == "speech_started":
            self._speaking = True
            self._speaking_since = now
            duration = event.get("duration")
            if isinstance(duration, (int, float)) and duration > 0:
                self._pending[uid] = now + duration + self.max_extra_s
        elif type_ == "speech_ended":
            self._speaking = False
            self._pending.pop(uid, None)
            if event.get("reason") not in NO_TAIL_REASONS:
                self._closed_until = now + self.tail_s
            if not self._pending:
                self._expected_end = now
        elif type_ == "error" and event.get("code") in NO_PLAYBACK_ERRORS:
            self._pending.pop(uid, None)
        elif type_ in ("ready", "shutdown"):
            # Plugin (re)started or stopping: nothing can be playing.
            self.force_open()

    @property
    def is_speaking(self) -> bool:
        return self._speaking

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
        self._expected_end = 0.0
