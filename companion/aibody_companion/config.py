"""Companion configuration. Loaded from a JSON file (see config.example.json);
command line flags override file values. Secrets (API keys) belong in environment
variables, never in this file or the repository."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

PLUGIN_DATA_SUBDIR = "Saves/PluginData/AIBody"

# Engines this companion version can run (reported to the AIBody plugin's engine menus).
# null / echo / tone are offline test engines and the default fallbacks; xai and elevenlabs need
# an API key (environment variable or key file, see pipeline/engines.py) and network access.
ENGINES_AVAILABLE: dict[str, list[str]] = {
    "stt": ["null", "xai"],
    "llm": ["echo", "xai"],
    "tts": ["tone", "xai", "elevenlabs"],
}


@dataclass
class Config:
    vam_root: str = ""  # VaM install folder (the one containing VaM.exe)
    channel: str = "default"  # must match the AIBody plugin's "Channel"
    poll_interval_s: float = 0.02

    sample_rate: int = 16000
    frame_ms: int = 30
    # Initial microphone settings (see audio/mic_settings.py). The plugin's Microphone menu
    # overrides them as soon as it connects.
    mic: dict[str, Any] = field(default_factory=dict)

    keep_audio_files: int = 20

    stt: str = "null"  # see ENGINES_AVAILABLE
    llm: str = "echo"
    tts: str = "tone"
    # Engine settings (persona, language, fallback, xai, elevenlabs): the "ai" section of the
    # shared config.json (settings_file.py). Empty = defaults.
    ai: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def channel_dir(self) -> Path:
        return Path(self.vam_root) / PLUGIN_DATA_SUBDIR / self.channel

    @property
    def has_vam_root(self) -> bool:
        return bool(self.vam_root)

    @property
    def audio_dir(self) -> Path:
        return self.channel_dir / "audio"

    def audio_rel_path(self, name: str) -> str:
        """Path the AIBody plugin loads with VaM's URLAudioClipManager (relative to the VaM folder)."""
        return f"{PLUGIN_DATA_SUBDIR}/{self.channel}/audio/{name}"

    def audio_abs_path(self, name: str) -> Path:
        return self.audio_dir / name

    def validate(self) -> list[str]:
        errors = []
        if not self.vam_root:
            errors.append("vam_root is required (path to the VaM folder; the plugin and this app share files there)")
        elif not Path(self.vam_root).is_dir():
            errors.append(f"vam_root does not exist: {self.vam_root}")
        for kind, name in (("stt", self.stt), ("llm", self.llm), ("tts", self.tts)):
            if name not in ENGINES_AVAILABLE[kind]:
                errors.append(f"{kind} engine {name!r} is not available (have: {ENGINES_AVAILABLE[kind]})")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: str | Path | None, overrides: dict[str, Any] | None = None) -> Config:
    data: dict[str, Any] = {}
    if path:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    known = {f.name for f in fields(Config)}
    cfg_kwargs = {k: v for k, v in data.items() if k in known}
    extra = {k: v for k, v in data.items() if k not in known}
    cfg = Config(**cfg_kwargs)
    cfg.extra.update(extra)
    for k, v in (overrides or {}).items():
        if v is not None and k in known:
            setattr(cfg, k, v)
    return cfg
