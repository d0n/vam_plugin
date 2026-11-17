"""Proactive timer: after `idle_seconds` without user speech and without AI speech, the companion
nudges the AI so it may say something on its own (or stay silent).

Each nudge in a row that the user does not answer doubles the wait (up to 8x), so a silent room
does not get a remark every minute. User speech resets that; AI speech only restarts the wait.
"""
from __future__ import annotations

import time
from collections.abc import Callable

MAX_BACKOFF_STEPS = 3  # 1x, 2x, 4x, 8x


class ProactiveTimer:
    def __init__(self, enabled: bool = False, idle_seconds: float = 90.0,
                 clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self.enabled = enabled
        self.idle_seconds = idle_seconds
        self.last_activity = clock()
        self.streak = 0  # nudges since the user last spoke

    def configure(self, enabled: bool, idle_seconds: float) -> None:
        if enabled and not self.enabled:
            self.last_activity = self._clock()  # switched on: count from now
        self.enabled = enabled
        self.idle_seconds = float(idle_seconds)

    def user_activity(self) -> None:
        self.last_activity = self._clock()
        self.streak = 0

    def ai_activity(self) -> None:
        self.last_activity = self._clock()

    @property
    def wait_s(self) -> float:
        return self.idle_seconds * (2 ** min(self.streak, MAX_BACKOFF_STEPS))

    def remaining(self) -> float:
        return max(0.0, self.wait_s - (self._clock() - self.last_activity))

    def due(self, can_speak: bool) -> bool:
        return self.enabled and can_speak and self._clock() - self.last_activity >= self.wait_s

    def fired(self) -> None:
        self.streak += 1
        self.last_activity = self._clock()
