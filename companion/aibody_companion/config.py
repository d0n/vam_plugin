"""Companion configuration. Loaded from a JSON file (see config.example.json);
command line flags override file values. Secrets (API keys) belong in environment
variables, never in this file or the repository."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

PLUGIN_DATA_SUBDIR = "Saves/PluginData/AIBody"


@dataclass
class Config:
    vam_root: str = ""  # VaM install folder (the one containing VaM.exe)
    channel: str = "Person"  # must match the plugin's "Channel" (defaults to the atom uid)
    transport: str = "file"  # "file" or "http"
    http_host: str = "127.0.0.1"
    http_port: int = 8765
    poll_interval_s: float = 0.05

    sample_rate: int = 16000
    frame_ms: int = 30
    mic_device: str | None = None
    vad_ratio: float = 3.0
    vad_min_rms: float = 0.01
    start_ms: int = 90
    end_silence_ms: int = 700
    max_utterance_ms: int = 20000

    echo_tail_s: float = 0.4
    keep_audio_files: int = 20

    stt: str = "null"  # TODO: "faster-whisper", "vosk", ...
    llm: str = "echo"  # TODO: "ollama", "openai", ...
    tts: str = "tone"  # TODO: "piper", "xtts", ...
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def channel_dir(self) -> Path:
        return Path(self.vam_root) / PLUGIN_DATA_SUBDIR / self.channel

    def audio_rel_path(self, name: str) -> str:
        """Path the plugin uses (relative to the VaM folder, forward slashes)."""
        return f"{PLUGIN_DATA_SUBDIR}/{self.channel}/audio/{name}"

    def audio_abs_path(self, name: str) -> Path:
        return self.channel_dir / "audio" / name

    def validate(self) -> list[str]:
        errors = []
        if not self.vam_root:
            errors.append("vam_root is not set (path to the VaM folder)")
        elif not Path(self.vam_root).is_dir():
            errors.append(f"vam_root does not exist: {self.vam_root}")
        if self.transport not in ("file", "http"):
            errors.append("transport must be 'file' or 'http'")
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
