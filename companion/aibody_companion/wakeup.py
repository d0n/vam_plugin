"""Wakes the app's main loop as soon as there is work (version 36, latency).

The main loop used to sleep a fixed poll interval (20 ms) between ticks, so every hand-over between threads - a
finished answer sentence from the turn worker, a datagram from the plugin (push-to-talk release, speech_started),
a microphone frame, a typed line - waited 10 ms on average and up to 20 ms before the tick saw it. Now these threads
call notify() and the loop's wait() returns at once; the poll interval stays the longest sleep (file channel,
timers).
"""
from __future__ import annotations

import threading

_EVENT = threading.Event()


def notify() -> None:
    """Called from any thread when something for the main loop arrived."""
    _EVENT.set()


def wait(timeout: float) -> bool:
    """Sleeps until notify() or `timeout` seconds; True if woken. Clears the signal BEFORE the caller's tick, so a
    notify() during the tick makes the next wait() return immediately (nothing is lost)."""
    woken = _EVENT.wait(timeout)
    _EVENT.clear()
    return woken
