"""Speech to text. Plug in a real engine by implementing SpeechToText.

TODO: implement one of
  * faster-whisper (local, GPU or CPU)      https://github.com/SYSTRAN/faster-whisper
  * Vosk (local, light, streaming)          https://alphacephei.com/vosk/
  * a cloud API (keys via environment variables, never committed)
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
