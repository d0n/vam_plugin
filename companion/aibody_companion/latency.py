"""Latency metric: end of the user's speech -> first audible sound (the plugin's speech_started).

Start (t0): VAD end of the utterance or push-to-talk release (the utterance is handed over), the
Enter of a typed line, or realtime's input_audio_buffer.speech_stopped. End: the plugin reports
speech_started for the first WAV of the answer (VaM really plays it). All times on the
companion's clock; the breakdown is the time between the steps that happened, in this order:

  chain:    STT, LLM erstes Token, erster Satz, TTS, Datei, an Plugin, Plugin-Start
  realtime: Server erstes Audio, Segment, an Plugin, Plugin-Start

"an Plugin" = until the speak command is written, "Plugin-Start" = from there until VaM plays
(file pickup, loading the WAV, start of the head audio).
"""
from __future__ import annotations

import threading
from collections import deque
from typing import Any

STEPS = [
    ("stt", "STT"),
    ("llm_first_token", "LLM erstes Token"),
    ("first_sentence", "erster Satz"),
    ("tts", "TTS"),
    ("write", "Datei"),
    ("first_audio", "Server erstes Audio"),
    ("segment", "Segment"),
    ("speak_sent", "an Plugin"),
    ("play", "Plugin-Start"),
]
LABELS = dict(STEPS)
KEEP = 10


class LatencyTrace:
    def __init__(self, t0: float, kind: str):
        self.t0 = t0
        self.kind = kind
        self.marks: dict[str, float] = {}
        self.done = False

    def mark(self, step: str, t: float) -> None:
        if step not in self.marks and not self.done:
            self.marks[step] = t

    def finish(self, t: float) -> dict[str, Any] | None:
        if self.done:
            return None
        self.mark("play", t)
        self.done = True
        parts: dict[str, float] = {}
        last = self.t0
        for step, _ in STEPS:
            if step in self.marks:
                at = max(self.marks[step], last)
                parts[step] = round(at - last, 3)
                last = at
        return {"kind": self.kind, "total_s": round(self.marks["play"] - self.t0, 3), "parts": parts}


def describe(result: dict[str, Any]) -> str:
    parts = " · ".join(f"{LABELS[k]} {v:.2f}" for k, v in result["parts"].items())
    return f"{result['total_s']:.2f} s ({parts})"


class LatencyStats:
    """The last value and a rolling average over the last KEEP turns."""

    def __init__(self, keep: int = KEEP):
        self._values: deque[dict[str, Any]] = deque(maxlen=keep)
        self._lock = threading.Lock()

    def add(self, result: dict[str, Any]) -> None:
        with self._lock:
            self._values.append(result)

    def info(self) -> dict[str, Any] | None:
        with self._lock:
            if not self._values:
                return None
            last = self._values[-1]
            avg = sum(v["total_s"] for v in self._values) / len(self._values)
            return {"last_s": last["total_s"], "avg_s": round(avg, 3), "n": len(self._values),
                    "kind": last["kind"], "parts": {LABELS[k]: v for k, v in last["parts"].items()}}
