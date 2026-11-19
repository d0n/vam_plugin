"""Microphone settings, as configured in the plugin's "Microphone" menu.

The plugin sends them in a `config` event ({"mic": {...}}); apply_mic_config() validates,
clamps to safe ranges and returns the settings the companion actually uses, which are sent
back in `config_ack`.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, fields, replace
from typing import Any

from ..vamjson import as_bool, as_number

log = logging.getLogger(__name__)

MODES = ("vad", "ptt")
VAD_ENGINES = ("auto", "energy", "webrtc", "silero")  # same as vad.VAD_ENGINES (kept here: no import cycle)

# Settings that no longer exist; old scenes / config.json files may still carry them. Ignored silently.
RETIRED = ("device",)  # input device name: the system default input is always used

# field -> (min, max) for numeric settings
LIMITS: dict[str, tuple[float, float]] = {
    "vad_threshold": (0.001, 0.5),
    "end_silence_ms": (200, 5000),
    "min_utterance_ms": (100, 5000),
    "max_utterance_ms": (1000, 60000),
    "echo_tail_s": (0.0, 3.0),
    "gain": (0.1, 8.0),
    "vad_strictness": (0, 3),
}


@dataclass(frozen=True)
class MicSettings:
    enabled: bool = True
    mode: str = "vad"  # "vad" (voice activation) or "ptt" (push-to-talk)
    vad_threshold: float = 0.01  # RMS 0..1 above which a frame counts as speech (a floor for every VAD engine)
    vad_engine: str = "auto"  # "auto" (silero if its model file is there, else webrtcvad if installed, else built-in), "energy", "webrtc", "silero"
    vad_strictness: int = 2  # 0..3: higher = ignores more background noise (webrtcvad mode; energy: start ratio)
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
        if key in RETIRED:
            log.debug("mic setting %r is retired (the system default input is always used) - ignored", key)
            continue
        if key not in types:
            errors.append(f"unknown mic setting {key!r}")
            continue
        default = getattr(MicSettings(), key)
        if isinstance(default, bool):
            flag = as_bool(value)  # the plugin (VaM SimpleJSON) sends "true"/"false"
            if flag is None:
                errors.append(f"{key} must be true/false")
                continue
            changes[key] = flag
        elif isinstance(default, (int, float)):
            number = as_number(value)  # ... and numbers as strings
            if number is None:
                errors.append(f"{key} must be a number")
                continue
            value = number
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
            if key == "vad_engine" and value not in VAD_ENGINES:
                errors.append(f"vad_engine must be one of {VAD_ENGINES}")
                continue
            changes[key] = value
    updated = replace(current, **changes)
    if updated.min_utterance_ms >= updated.max_utterance_ms:
        errors.append("min_utterance_ms must be smaller than max_utterance_ms")
        updated = replace(updated, min_utterance_ms=current.min_utterance_ms, max_utterance_ms=current.max_utterance_ms)
    return updated, errors
