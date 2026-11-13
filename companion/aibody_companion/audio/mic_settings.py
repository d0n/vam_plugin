"""Microphone settings, as configured in the plugin's "Microphone" menu.

The plugin sends them in a `config` event ({"mic": {...}}); apply_mic_config() validates,
clamps to safe ranges and returns the settings the companion actually uses, which are sent
back in `config_ack`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from typing import Any

MODES = ("vad", "ptt")

# field -> (min, max) for numeric settings
LIMITS: dict[str, tuple[float, float]] = {
    "vad_threshold": (0.001, 0.5),
    "end_silence_ms": (200, 5000),
    "min_utterance_ms": (100, 5000),
    "max_utterance_ms": (1000, 60000),
    "echo_tail_s": (0.0, 3.0),
    "gain": (0.1, 8.0),
}


@dataclass(frozen=True)
class MicSettings:
    enabled: bool = True
    mode: str = "vad"  # "vad" (voice activation) or "ptt" (push-to-talk)
    device: str = ""  # input device name, "" = system default
    vad_threshold: float = 0.01  # RMS 0..1 above which a frame counts as speech
    end_silence_ms: int = 700  # silence that ends an utterance
    min_utterance_ms: int = 300  # shorter utterances are dropped
    max_utterance_ms: int = 20000  # longer utterances are cut
    echo_tail_s: float = 0.4  # mic stays closed this long after the body stopped speaking
    gain: float = 1.0  # input gain applied before VAD and STT
    ptt_interrupts: bool = True  # pressing push-to-talk stops the body's speech
    level_meter: bool = True  # stream mic_level messages to the plugin

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def apply_mic_config(current: MicSettings, data: Any) -> tuple[MicSettings, list[str]]:
    """Returns (new settings, errors). Invalid fields keep their current value."""
    if not isinstance(data, dict):
        return current, ["mic config must be an object"]
    errors: list[str] = []
    types = {f.name: f.type for f in fields(MicSettings)}
    changes: dict[str, Any] = {}
    for key, value in data.items():
        if key not in types:
            errors.append(f"unknown mic setting {key!r}")
            continue
        default = getattr(MicSettings(), key)
        if isinstance(default, bool):
            if not isinstance(value, bool):
                errors.append(f"{key} must be true/false")
                continue
            changes[key] = value
        elif isinstance(default, (int, float)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"{key} must be a number")
                continue
            lo, hi = LIMITS[key]
            value = min(max(value, lo), hi)
            changes[key] = int(round(value)) if isinstance(default, int) else float(value)
        else:
            if not isinstance(value, str):
                errors.append(f"{key} must be a string")
                continue
            if key == "mode" and value not in MODES:
                errors.append(f"mode must be one of {MODES}")
                continue
            changes[key] = value
    updated = replace(current, **changes)
    if updated.min_utterance_ms >= updated.max_utterance_ms:
        errors.append("min_utterance_ms must be smaller than max_utterance_ms")
        updated = replace(updated, min_utterance_ms=current.min_utterance_ms, max_utterance_ms=current.max_utterance_ms)
    return updated, errors
