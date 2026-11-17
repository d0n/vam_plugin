"""Speech to text. Engines implement SpeechToText; the real one is xai.XaiStt (see engines.py).
NullStt is the offline placeholder and the default fallback.
"""
from __future__ import annotations

from typing import Protocol


class SpeechToText(Protocol):
    def transcribe(self, pcm16: bytes, sample_rate: int) -> str:
        """Returns the recognized text ("" if nothing was understood)."""
        ...


class NullStt:
    """Placeholder that recognizes nothing; lets the audio path run end to end."""

    def transcribe(self, pcm16: bytes, sample_rate: int) -> str:
        return ""
