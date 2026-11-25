"""Grok Bot bridge (version 61): an optional second way to drive the AI character, next to the direct method.

Two drivers, chosen with config.json ``ai.driver``:

  * ``direct`` (the default, unchanged): this app's own AI answers (speech recognition -> language model / realtime ->
    text to speech), exactly as up to version 60.
  * ``grok_bot``: Grok Bot (the desktop app, running on this computer with local execution allowed) is the brain. This
    app still listens (microphone, speech recognition, mute words, pose commands) and still speaks, but it asks no
    language model and opens no realtime session: what the user says and the scene events go into a small event queue
    that Grok Bot reads over the remote control's HTTP API on 127.0.0.1 (``GET /api/bridge/events``), and Grok Bot
    answers with the existing actions (``POST /api/say``, ``/api/expression``, ``/api/gesture``, ``/api/pose``,
    ``/api/look``, ``/api/stop``). See docs/GROK_BOT_BRIDGE.md.

The bridge needs the remote control (``remote.enabled``, token): without it ``grok_bot`` falls back to ``direct`` with
a warning, so a half-configured bridge never leaves the character without an AI. Switching back is one key
(``ai.driver: "direct"``) and a restart of the app; nothing of the direct method was removed.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

DIRECT = "direct"
GROK_BOT = "grok_bot"
DRIVERS = (DIRECT, GROK_BOT)

MAX_EVENTS = 200  # kept for late readers; older ones are dropped (the reader sees the gap in the ids)
MAX_WAIT_S = 25.0  # longest long-poll of GET /api/bridge/events?wait=...
EVENT_TYPES = ("user_said", "scene_event", "plugin")


def normalize_driver(value: Any) -> str:
    """'direct' or 'grok_bot' (anything else, also empty, is the direct method)."""
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return GROK_BOT if text in (GROK_BOT, "grokbot") else DIRECT


class BridgeQueue:
    """Thread-safe event list with increasing ids. The main loop pushes, the HTTP threads read (optionally waiting)."""

    def __init__(self, clock: Callable[[], float] = time.time, max_events: int = MAX_EVENTS):
        self._clock = clock
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._next_id = 1
        self._cond = threading.Condition()

    @property
    def last_id(self) -> int:
        with self._cond:
            return self._next_id - 1

    def push(self, type_: str, **fields: Any) -> dict[str, Any]:
        if type_ not in EVENT_TYPES:
            raise ValueError(f"unknown bridge event type {type_!r}")
        with self._cond:
            event = {"id": self._next_id, "type": type_, "time": round(self._clock(), 3), **fields}
            self._next_id += 1
            self._events.append(event)
            self._cond.notify_all()
            return dict(event)

    def since(self, after: int, wait_s: float = 0.0) -> list[dict[str, Any]]:
        """The events with an id above `after` (oldest first). With wait_s > 0 waits up to that long for one."""
        wait_s = max(0.0, min(float(wait_s), MAX_WAIT_S))
        deadline = time.monotonic() + wait_s
        with self._cond:
            while True:
                found = [dict(e) for e in self._events if e["id"] > after]
                left = deadline - time.monotonic()
                if found or left <= 0:
                    return found
                self._cond.wait(timeout=left)
