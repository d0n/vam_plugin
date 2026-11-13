"""Companion configuration. Loaded from a JSON file (see config.example.json);
command line flags override file values. Secrets (API keys) belong in environment
variables, never in this file or the repository."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

PLUGIN_DATA_SUBDIR = "Saves/PluginData/AIBody"

# Engines this companion version can run (reported to the Session plugin's engine menus).
ENGINES_AVAILABLE: dict[str, list[str]] = {"stt": ["null"], "llm": ["echo"], "tts": ["tone"]}


@dataclass
class Config:
    vam_root: str = ""  # VaM install folder (the one containing VaM.exe)
    channel: str = "default"  # must match the Session plugin's "Channel"
    # "file" (default; the only link the default VaM build supports). "http" / "auto" only work
    # with a plugin built with AIBODY_HTTP (see README).
    transport: str = "file"
    # Character slot the AI speaks through: "person1" (d0n.AIBodyPerson on character 1) or
    # "person2" (d0n.AIBodyPerson2 on character 2); "" = the Session plugin's "Default slot".
    default_slot: str = ""
    http_host: str = "127.0.0.1"
    http_port: int = 8765
    poll_interval_s: float = 0.02
    audio_cache_dir: str = ""  # where TTS audio goes if vam_root is not set (HTTP only)

    sample_rate: int = 16000
    frame_ms: int = 30
    # Initial microphone settings (see audio/mic_settings.py). The plugin's Microphone menu
    # overrides them as soon as it connects.
    mic: dict[str, Any] = field(default_factory=dict)

    keep_audio_files: int = 20

    stt: str = "null"  # TODO: "faster-whisper", "vosk", ...
    llm: str = "echo"  # TODO: "ollama", "openai", ...
    tts: str = "tone"  # TODO: "piper", "xtts", ...
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def channel_dir(self) -> Path:
        return Path(self.vam_root) / PLUGIN_DATA_SUBDIR / self.channel

    @property
    def has_vam_root(self) -> bool:
        return bool(self.vam_root)

    @property
    def audio_dir(self) -> Path:
        if self.vam_root:
            return self.channel_dir / "audio"
        if self.audio_cache_dir:
            return Path(self.audio_cache_dir)
        return Path.home() / ".cache" / "aibody" / "audio" / self.channel

    def audio_rel_path(self, name: str) -> str | None:
        """Path the Person plugin can load directly (relative to the VaM folder), if vam_root is set."""
        return f"{PLUGIN_DATA_SUBDIR}/{self.channel}/audio/{name}" if self.vam_root else None

    def audio_abs_path(self, name: str) -> Path:
        return self.audio_dir / name

    def validate(self) -> list[str]:
        errors = []
        if self.transport not in ("auto", "file", "http"):
            errors.append("transport must be 'auto', 'http' or 'file'")
        if self.vam_root and not Path(self.vam_root).is_dir():
            errors.append(f"vam_root does not exist: {self.vam_root}")
        if self.transport == "file" and not self.vam_root:
            errors.append("the file transport needs vam_root (path to the VaM folder)")
        if self.default_slot not in ("", "person1", "person2"):
            errors.append("default_slot must be 'person1', 'person2' or ''")
        for kind, name in (("stt", self.stt), ("llm", self.llm), ("tts", self.tts)):
            if name not in ENGINES_AVAILABLE[kind]:
                errors.append(f"{kind} engine {name!r} is not available (have: {ENGINES_AVAILABLE[kind]})")
        if not (1 <= self.http_port <= 65535):
            errors.append("http_port must be 1..65535")
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
